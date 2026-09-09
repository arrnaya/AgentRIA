import httpx
import respx

from agents.recon import run_recon
from graph.subgraph_client import SUBGRAPH_IDS, SubgraphClient
from pipeline.state import RiaState, SignalType

API_KEY = "test-key"


def _endpoint(subgraph_key: str) -> str:
    return f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_IDS[subgraph_key]}"


DEX_RESPONSE = {
    "data": {
        "liquidityPools": [
            {
                "id": "0xpool1",
                "name": "Uniswap V3 ETH/USDC",
                "inputTokens": [{"symbol": "WETH"}, {"symbol": "USDC"}],
                "totalValueLockedUSD": "1000000",
                "cumulativeVolumeUSD": "5000000",
                "fees": [{"feePercentage": "0.3", "feeType": "FIXED_TRADING_FEE"}],
            }
        ]
    }
}

LENDING_RESPONSE_HIGH_UTIL = {
    "data": {
        "markets": [
            {
                "id": "0xmarket1",
                "name": "Aave V3 USDC",
                "inputToken": {"symbol": "USDC"},
                "totalValueLockedUSD": "2000000",
                "totalDepositBalanceUSD": "1000000",
                "totalBorrowBalanceUSD": "900000",
                "rates": [{"rate": "3.2", "side": "BORROWER", "type": "VARIABLE"}],
            }
        ]
    }
}


@respx.mock
async def test_run_recon_normalizes_dex_and_lending_signals():
    respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=DEX_RESPONSE)
    )
    respx.post(_endpoint("aave-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=LENDING_RESPONSE_HIGH_UTIL)
    )

    state = RiaState()
    client = SubgraphClient(api_key=API_KEY)

    result = await run_recon(state, client=client)

    assert result is state
    assert len(state.signals) == 2

    dex_signal = next(s for s in state.signals if s["id"] == "dex:0xpool1")
    assert dex_signal["protocol"] == "Uniswap v3"
    assert dex_signal["pair"] == "WETH/USDC"
    assert dex_signal["type"] == SignalType.YIELD_GAP
    assert dex_signal["raw_metrics"]["totalValueLockedUSD"] == 1_000_000.0

    lending_signal = next(s for s in state.signals if s["id"] == "lending:0xmarket1")
    assert lending_signal["protocol"] == "Aave v3"
    assert lending_signal["pair"] == "USDC"
    # 900k borrowed / 1m deposited = 0.9 utilization -> above the 0.8 cutoff
    assert lending_signal["type"] == SignalType.LIQUIDATION_PROXIMITY
    assert lending_signal["raw_metrics"]["utilization"] == 0.9


@respx.mock
async def test_run_recon_flags_rate_divergence_below_utilization_cutoff():
    respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json={"data": {"liquidityPools": []}})
    )
    low_util_response = {
        "data": {
            "markets": [
                {
                    "id": "0xmarket2",
                    "name": "Aave V3 DAI",
                    "inputToken": {"symbol": "DAI"},
                    "totalValueLockedUSD": "500000",
                    "totalDepositBalanceUSD": "500000",
                    "totalBorrowBalanceUSD": "100000",
                    "rates": [],
                }
            ]
        }
    }
    respx.post(_endpoint("aave-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=low_util_response)
    )

    state = RiaState()
    await run_recon(state, client=SubgraphClient(api_key=API_KEY))

    lending_signal = state.signals[0]
    assert lending_signal["type"] == SignalType.RATE_DIVERGENCE
