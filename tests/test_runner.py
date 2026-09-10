import asyncio
import json

import httpx
import respx
from websockets.asyncio.client import connect

from graph.subgraph_client import SUBGRAPH_IDS, SubgraphClient
from pipeline.runner import _trace_for_node, main_loop, parse_args, run_cycle
from pipeline.state import RiaState
from pipeline.ws_server import RiaWsServer

API_KEY = "test-key"


def _endpoint(subgraph_key: str) -> str:
    return f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_IDS[subgraph_key]}"


HIGH_SIGNAL_DEX_RESPONSE = {
    "data": {
        "liquidityPools": [
            {
                "id": "0xdeep",
                "name": "Deep Pool",
                "inputTokens": [{"symbol": "WETH"}, {"symbol": "USDC"}],
                "totalValueLockedUSD": "10000000",
                "cumulativeVolumeUSD": "40000000",
                "fees": [],
            }
        ]
    }
}
EMPTY_DEX_RESPONSE = {"data": {"liquidityPools": []}}
EMPTY_LENDING_RESPONSE = {"data": {"markets": []}}


def _mock_recon_endpoints(dex_response=EMPTY_DEX_RESPONSE, lending_response=EMPTY_LENDING_RESPONSE):
    respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=dex_response)
    )
    respx.post(_endpoint("aave-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=lending_response)
    )


def test_parse_args_matches_readme_flag_names_exactly():
    args = parse_args(
        [
            "--mode", "live",
            "--networks", "ethereum,arbitrum,polygon",
            "--risk-threshold", "0.65",
            "--budget-hbar", "10",
            "--interval", "30",
            "--ws-port", "3001",
            "--mcp-server", "http://localhost:8080",
        ]
    )

    assert args.mode == "live"
    assert args.networks == "ethereum,arbitrum,polygon"
    assert args.risk_threshold == 0.65
    assert args.budget_hbar == 10.0
    assert args.interval == 30
    assert args.ws_port == 3001
    assert args.mcp_server == "http://localhost:8080"


def test_parse_args_defaults():
    args = parse_args([])

    assert args.mode == "live"
    assert args.networks == "ethereum"
    assert args.risk_threshold == 0.65
    assert args.budget_hbar == 10.0
    assert args.interval == 30
    assert args.ws_port == 3001
    assert args.mcp_server is None


def test_trace_for_node_recon():
    status, note = _trace_for_node("recon", {"signals": [1, 2]}, 0.65)
    assert status == "Complete"
    assert "2" in note


def test_trace_for_node_risk_counts_above_threshold():
    values = {
        "assessments": [
            {"above_threshold": True},
            {"above_threshold": False},
        ]
    }
    status, note = _trace_for_node("risk", values, 0.65)
    assert status == "1/2 above threshold"
    assert "0.65" in note


def test_trace_for_node_unknown_node_defaults_gracefully():
    status, note = _trace_for_node("mystery", {}, 0.65)
    assert status == "Complete"
    assert note == ""


@respx.mock
async def test_run_cycle_streams_trace_and_signal_events():
    _mock_recon_endpoints(dex_response=HIGH_SIGNAL_DEX_RESPONSE)

    server = RiaWsServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        uri = f"ws://127.0.0.1:{server.bound_port}"
        async with connect(uri) as client:
            await asyncio.sleep(0.05)

            state = RiaState(risk_threshold=0.1)
            client_sub = SubgraphClient(api_key=API_KEY)
            result = await run_cycle(state, server, recon_client=client_sub)

            assert isinstance(result, RiaState)
            assert len(result.signals) == 1

            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(client.recv(), timeout=0.5)
                    events.append(json.loads(raw))
            except asyncio.TimeoutError:
                pass

            event_types = [e["event"] for e in events]
            # One TRACE per node that ran: recon, scout, risk, oracle, exec, audit
            assert event_types.count("TRACE") == 6
            assert "SIGNAL" in event_types
            signal_events = [e for e in events if e["event"] == "SIGNAL"]
            assert signal_events[0]["data"]["protocol"] == "Uniswap v3"
    finally:
        await server.stop()


@respx.mock
async def test_run_cycle_alert_branch_emits_alert_trace_not_oracle():
    _mock_recon_endpoints()

    server = RiaWsServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        uri = f"ws://127.0.0.1:{server.bound_port}"
        async with connect(uri) as client:
            await asyncio.sleep(0.05)

            state = RiaState(risk_threshold=0.65)
            client_sub = SubgraphClient(api_key=API_KEY)
            await run_cycle(state, server, recon_client=client_sub)

            events = []
            try:
                while True:
                    raw = await asyncio.wait_for(client.recv(), timeout=0.5)
                    events.append(json.loads(raw))
            except asyncio.TimeoutError:
                pass

            trace_names = [e["data"]["name"] for e in events if e["event"] == "TRACE"]
            assert "ALERT" in trace_names
            assert "ORACLE" not in trace_names
    finally:
        await server.stop()


@respx.mock
async def test_main_loop_runs_bounded_cycles_and_shuts_down(monkeypatch):
    _mock_recon_endpoints()
    monkeypatch.setenv("GRAPH_API_KEY", API_KEY)

    args = parse_args(["--ws-port", "0", "--interval", "0"])
    await main_loop(args, max_cycles=1)
    # If we get here without hanging or raising, the server started and
    # stopped cleanly around exactly one pipeline cycle.
