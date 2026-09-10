import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from pipeline.state import OpportunitySignal, SignalType, now_iso
from pipeline.ws_server import (
    RiaWsServer,
    audit_payload,
    payment_payload,
    signal_payload,
    trace_payload,
)


def _signal(signal_type: SignalType = SignalType.YIELD_GAP) -> OpportunitySignal:
    return OpportunitySignal(
        id="dex:1",
        protocol="Uniswap v3",
        network="ethereum",
        pair="WETH/USDC",
        type=signal_type,
        raw_metrics={},
        source="test",
        observed_at=now_iso(),
    )


def test_signal_payload_matches_dashboard_mock_shape():
    payload = signal_payload(_signal(SignalType.COLLATERAL_DRIFT), rank_score=0.734567)

    assert payload["protocol"] == "Uniswap v3"
    assert payload["pair"] == "WETH/USDC"
    assert payload["type"] == "collateral_drift"
    # Exact label used in src/app/app/page.tsx's mock opportunities array.
    assert payload["type_label"] == "Collateral ratio drift"
    assert payload["confidence"] == 0.7346


def test_trace_payload_matches_dashboard_mock_shape():
    payload = trace_payload("RISK", "Routed → ORACLE", "Confidence 0.71, above 0.65 threshold")

    assert payload == {
        "name": "RISK",
        "status": "Routed → ORACLE",
        "note": "Confidence 0.71, above 0.65 threshold",
    }


def test_payment_payload_reads_assumed_oracle_enrichment_shape():
    enrichment = {
        "signal_id": "dex:1",
        "tool": "get_risk_score",
        "confidence_delta": 0.03,
        "hbar_cost": 0.002,
        "tx_id": "0.0.1234@1700000000.000000001",
        "enriched_at": now_iso(),
    }

    payload = payment_payload(enrichment)

    assert payload["tool"] == "get_risk_score"
    assert payload["amount_hbar"] == 0.002
    assert payload["facilitator"] == "Blocky402"
    assert payload["tx_id"] == "0.0.1234@1700000000.000000001"
    assert payload["status"] == "confirmed"


def test_payment_payload_pending_status_without_tx_id():
    payload = payment_payload({"tool": "get_risk_score"})

    assert payload["status"] == "pending"
    assert payload["tx_id"] is None


def test_audit_payload_reads_defensively_from_unknown_shape():
    payload = audit_payload({"note": "logged"})

    assert payload["action"] == "AUDIT"
    assert payload["note"] == "logged"
    assert payload["logged_at"]  # defaulted, not missing


def test_emit_raises_on_unknown_event_type():
    server = RiaWsServer()
    with pytest.raises(ValueError):
        server.emit("UNKNOWN", {})


def test_emit_is_a_noop_with_no_connected_clients():
    server = RiaWsServer()
    # Should not raise even though start() was never called / no clients.
    server.emit("SIGNAL", {"protocol": "Uniswap v3"})


async def test_server_broadcasts_emitted_event_to_connected_client():
    server = RiaWsServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        uri = f"ws://127.0.0.1:{server.bound_port}"
        async with connect(uri) as client:
            # give the server a beat to register the connection
            await asyncio.sleep(0.05)
            server.emit("TRACE", trace_payload("RECON", "Complete", "Pulled 2 signals"))

            raw = await asyncio.wait_for(client.recv(), timeout=2.0)
            message = json.loads(raw)

            assert message["event"] == "TRACE"
            assert message["data"]["name"] == "RECON"
            assert "ts" in message
    finally:
        await server.stop()


async def test_server_supports_multiple_clients():
    server = RiaWsServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        uri = f"ws://127.0.0.1:{server.bound_port}"
        async with connect(uri) as client_a, connect(uri) as client_b:
            await asyncio.sleep(0.05)
            server.emit("SIGNAL", signal_payload(_signal(), rank_score=0.5))

            raw_a = await asyncio.wait_for(client_a.recv(), timeout=2.0)
            raw_b = await asyncio.wait_for(client_b.recv(), timeout=2.0)

            assert json.loads(raw_a)["event"] == "SIGNAL"
            assert json.loads(raw_b)["event"] == "SIGNAL"
    finally:
        await server.stop()
