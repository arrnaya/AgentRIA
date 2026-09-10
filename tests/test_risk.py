import pytest

from agents.risk import run_risk
from pipeline.state import (
    OpportunitySignal,
    RankedOpportunity,
    RiaState,
    SignalType,
    now_iso,
)


def _ranked(
    id: str,
    raw_metrics: dict,
    rank_score: float,
    signal_type: SignalType = SignalType.YIELD_GAP,
) -> RankedOpportunity:
    signal = OpportunitySignal(
        id=id,
        protocol="Test Protocol",
        network="ethereum",
        pair="WETH/USDC",
        type=signal_type,
        raw_metrics=raw_metrics,
        source="test",
        observed_at=now_iso(),
    )
    return RankedOpportunity(signal=signal, rank_score=rank_score)


async def test_deep_liquidity_signal_keeps_full_rank_score_as_confidence():
    state = RiaState()
    # TVL >= LIQUIDITY_REFERENCE_USD (2,000,000) -> liquidity_factor = 1.0
    state.ranked.append(
        _ranked("dex:1", {"totalValueLockedUSD": 5_000_000.0}, rank_score=0.8)
    )

    result = await run_risk(state)

    assert result is state
    assert len(state.assessments) == 1
    assert state.assessments[0]["confidence"] == pytest.approx(0.8)


async def test_shallow_liquidity_signal_discounts_confidence():
    state = RiaState()
    # TVL is 1/4 of the reference -> liquidity_factor = 0.25
    state.ranked.append(
        _ranked("dex:2", {"totalValueLockedUSD": 500_000.0}, rank_score=1.0)
    )

    await run_risk(state)

    assert state.assessments[0]["confidence"] == pytest.approx(0.25)


async def test_position_size_capped_by_liquidity_share():
    state = RiaState()
    # TVL 1,000,000 * 1% share = 10,000 cap; confidence = 1.0 * (1M/2M) = 0.5
    state.ranked.append(
        _ranked("dex:3", {"totalValueLockedUSD": 1_000_000.0}, rank_score=1.0)
    )

    await run_risk(state)

    assessment = state.assessments[0]
    assert assessment["confidence"] == pytest.approx(0.5)
    # position_size_usd = confidence * min(liquidity*1%, 50k) = 0.5 * 10,000
    assert assessment["position_size_usd"] == pytest.approx(5_000.0)


async def test_position_size_never_exceeds_hard_cap():
    state = RiaState()
    # TVL huge enough that 1% would exceed the $50k hard cap.
    state.ranked.append(
        _ranked(
            "dex:4",
            {"totalValueLockedUSD": 20_000_000.0},
            rank_score=1.0,
        )
    )

    await run_risk(state)

    assessment = state.assessments[0]
    assert assessment["confidence"] == pytest.approx(1.0)
    assert assessment["position_size_usd"] == pytest.approx(50_000.0)


async def test_above_threshold_flag_uses_state_risk_threshold():
    state = RiaState(risk_threshold=0.5)
    state.ranked.append(
        _ranked("dex:5", {"totalValueLockedUSD": 2_000_000.0}, rank_score=0.6)
    )
    state.ranked.append(
        _ranked("dex:6", {"totalValueLockedUSD": 2_000_000.0}, rank_score=0.3)
    )

    await run_risk(state)

    high = next(a for a in state.assessments if a["opportunity"]["signal"]["id"] == "dex:5")
    low = next(a for a in state.assessments if a["opportunity"]["signal"]["id"] == "dex:6")
    assert high["above_threshold"] is True
    assert low["above_threshold"] is False


async def test_lending_signal_uses_deposits_as_liquidity_proxy():
    state = RiaState()
    state.ranked.append(
        _ranked(
            "lending:1",
            {"totalDepositBalanceUSD": 4_000_000.0},
            rank_score=0.5,
            signal_type=SignalType.LIQUIDATION_PROXIMITY,
        )
    )

    await run_risk(state)

    # TVL/deposits >= reference -> full liquidity factor
    assert state.assessments[0]["confidence"] == pytest.approx(0.5)


async def test_run_risk_does_not_double_assess_existing_opportunities():
    state = RiaState()
    state.ranked.append(
        _ranked("dex:7", {"totalValueLockedUSD": 2_000_000.0}, rank_score=0.9)
    )

    await run_risk(state)
    await run_risk(state)

    assert len(state.assessments) == 1
