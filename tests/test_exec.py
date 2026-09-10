import pytest

from agents.exec import run_exec
from pipeline.state import (
    OpportunitySignal,
    RankedOpportunity,
    RiaState,
    RiskAssessment,
    SignalType,
    now_iso,
)


def _assessment(
    signal_id: str,
    confidence: float,
    above_threshold: bool,
    position_size_usd: float = 1_000.0,
) -> RiskAssessment:
    signal = OpportunitySignal(
        id=signal_id,
        protocol="Uniswap v3",
        network="ethereum",
        pair="WETH/USDC",
        type=SignalType.YIELD_GAP,
        raw_metrics={},
        source="test",
        observed_at=now_iso(),
    )
    ranked = RankedOpportunity(signal=signal, rank_score=0.9)
    return RiskAssessment(
        opportunity=ranked,
        confidence=confidence,
        position_size_usd=position_size_usd,
        above_threshold=above_threshold,
    )


def _enrichment(signal_id: str, confidence_delta: float = 0.0) -> dict:
    return {
        "signal_id": signal_id,
        "tool": "get_risk_score",
        "confidence_delta": confidence_delta,
        "hbar_cost": 0.002,
        "tx_id": "0.0.1234@1700000000.000000001",
        "enriched_at": now_iso(),
    }


async def test_dispatches_action_when_above_threshold_and_enriched():
    state = RiaState(risk_threshold=0.65)
    state.assessments.append(_assessment("dex:1", confidence=0.8, above_threshold=True))
    state.enrichments.append(_enrichment("dex:1", confidence_delta=0.02))

    result = await run_exec(state)

    assert result is state
    assert len(state.actions) == 1
    action = state.actions[0]
    assert action["signal_id"] == "dex:1"
    assert action["status"] == "dispatched"
    assert action["confidence"] == pytest.approx(0.82)
    assert action["enrichment_tx_id"] == "0.0.1234@1700000000.000000001"


async def test_skips_when_risk_did_not_flag_above_threshold():
    state = RiaState()
    state.assessments.append(_assessment("dex:2", confidence=0.5, above_threshold=False))
    state.enrichments.append(_enrichment("dex:2"))

    await run_exec(state)

    assert state.actions == []


async def test_waits_when_no_oracle_enrichment_yet():
    state = RiaState()
    state.assessments.append(_assessment("dex:3", confidence=0.9, above_threshold=True))
    # no enrichment appended

    await run_exec(state)

    assert state.actions == []


async def test_skips_when_enrichment_downgrades_below_threshold():
    state = RiaState(risk_threshold=0.65)
    state.assessments.append(_assessment("dex:4", confidence=0.7, above_threshold=True))
    state.enrichments.append(_enrichment("dex:4", confidence_delta=-0.2))

    await run_exec(state)

    assert state.actions == []


async def test_run_exec_does_not_double_dispatch():
    state = RiaState()
    state.assessments.append(_assessment("dex:5", confidence=0.9, above_threshold=True))
    state.enrichments.append(_enrichment("dex:5"))

    await run_exec(state)
    await run_exec(state)

    assert len(state.actions) == 1


async def test_run_exec_handles_multiple_independent_assessments():
    state = RiaState(risk_threshold=0.65)
    state.assessments.append(_assessment("dex:6", confidence=0.9, above_threshold=True))
    state.assessments.append(_assessment("dex:7", confidence=0.5, above_threshold=False))
    state.enrichments.append(_enrichment("dex:6"))

    await run_exec(state)

    assert len(state.actions) == 1
    assert state.actions[0]["signal_id"] == "dex:6"
