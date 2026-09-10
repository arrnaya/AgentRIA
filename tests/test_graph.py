import httpx
import respx

from graph.subgraph_client import SUBGRAPH_IDS, SubgraphClient
from pipeline.graph import route_after_risk, run_pipeline
from pipeline.state import OpportunitySignal, RiaState, RiskAssessment, RankedOpportunity, SignalType, now_iso

API_KEY = "test-key"


def _endpoint(subgraph_key: str) -> str:
    return f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_IDS[subgraph_key]}"


# A deep, high-volume pool -> yield_gap signal that scores well above any
# reasonable threshold once ranked and risk-assessed.
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

EMPTY_LENDING_RESPONSE = {"data": {"markets": []}}
EMPTY_DEX_RESPONSE = {"data": {"liquidityPools": []}}


def _mock_recon_endpoints(dex_response=EMPTY_DEX_RESPONSE, lending_response=EMPTY_LENDING_RESPONSE):
    respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=dex_response)
    )
    respx.post(_endpoint("aave-v3-ethereum")).mock(
        return_value=httpx.Response(200, json=lending_response)
    )


@respx.mock
async def test_pipeline_runs_end_to_end_with_stubbed_oracle_and_audit():
    _mock_recon_endpoints(dex_response=HIGH_SIGNAL_DEX_RESPONSE)

    state = RiaState(risk_threshold=0.1)
    client = SubgraphClient(api_key=API_KEY)

    result = await run_pipeline(state, recon_client=client)

    assert isinstance(result, RiaState)
    assert len(result.signals) == 1
    assert len(result.ranked) == 1
    assert len(result.assessments) == 1
    assert result.assessments[0]["above_threshold"] is True
    # No agents/oracle.py in this tree yet -> stub passes through with zero
    # enrichments -> EXEC has nothing to dispatch (it waits, per its gates).
    assert result.enrichments == []
    assert result.actions == []


@respx.mock
async def test_pipeline_routes_to_alert_when_nothing_clears_threshold():
    _mock_recon_endpoints(dex_response=EMPTY_DEX_RESPONSE, lending_response=EMPTY_LENDING_RESPONSE)

    state = RiaState(risk_threshold=0.65)
    client = SubgraphClient(api_key=API_KEY)

    result = await run_pipeline(state, recon_client=client)

    assert result.signals == []
    assert result.assessments == []
    assert result.actions == []


@respx.mock
async def test_pipeline_dispatches_when_enrichment_preseeded():
    _mock_recon_endpoints(dex_response=HIGH_SIGNAL_DEX_RESPONSE)

    state = RiaState(risk_threshold=0.1)
    # Simulate ORACLE having already enriched this signal in a prior step —
    # the stub ORACLE node passes existing enrichments through untouched,
    # so EXEC should see it and dispatch.
    state.enrichments.append(
        {
            "signal_id": "dex:0xdeep",
            "tool": "get_risk_score",
            "confidence_delta": 0.0,
            "hbar_cost": 0.002,
            "tx_id": "0.0.999@1700000000.000000001",
            "enriched_at": now_iso(),
        }
    )
    client = SubgraphClient(api_key=API_KEY)

    result = await run_pipeline(state, recon_client=client)

    assert len(result.actions) == 1
    assert result.actions[0]["signal_id"] == "dex:0xdeep"
    assert result.actions[0]["status"] == "dispatched"


def _assessment(above_threshold: bool) -> RiskAssessment:
    signal = OpportunitySignal(
        id="x",
        protocol="p",
        network="ethereum",
        pair="A/B",
        type=SignalType.YIELD_GAP,
        raw_metrics={},
        source="test",
        observed_at=now_iso(),
    )
    ranked = RankedOpportunity(signal=signal, rank_score=0.9)
    return RiskAssessment(
        opportunity=ranked, confidence=0.9, position_size_usd=100.0, above_threshold=above_threshold
    )


def test_route_after_risk_goes_to_oracle_when_any_above_threshold():
    state = RiaState()
    state.assessments.append(_assessment(above_threshold=False))
    state.assessments.append(_assessment(above_threshold=True))

    assert route_after_risk(state) == "oracle"


def test_route_after_risk_goes_to_alert_when_none_above_threshold():
    state = RiaState()
    state.assessments.append(_assessment(above_threshold=False))

    assert route_after_risk(state) == "alert"


def test_route_after_risk_goes_to_alert_when_no_assessments():
    state = RiaState()

    assert route_after_risk(state) == "alert"
