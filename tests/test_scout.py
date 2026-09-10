import pytest

from agents.scout import run_scout
from pipeline.state import OpportunitySignal, RiaState, SignalType, now_iso


def _signal(
    id: str,
    signal_type: SignalType,
    raw_metrics: dict,
    protocol: str = "Test Protocol",
) -> OpportunitySignal:
    return OpportunitySignal(
        id=id,
        protocol=protocol,
        network="ethereum",
        pair="WETH/USDC",
        type=signal_type,
        raw_metrics=raw_metrics,
        source="test",
        observed_at=now_iso(),
    )


async def test_yield_gap_scored_by_volume_over_tvl():
    state = RiaState()
    state.signals.append(
        _signal(
            "dex:1",
            SignalType.YIELD_GAP,
            {"totalValueLockedUSD": 1_000_000.0, "cumulativeVolumeUSD": 2_500_000.0},
        )
    )

    result = await run_scout(state)

    assert result is state
    assert len(state.ranked) == 1
    # volume/tvl = 2.5, cap is 5.0 -> score = 0.5
    assert state.ranked[0]["rank_score"] == 0.5
    assert state.ranked[0]["signal"]["id"] == "dex:1"


async def test_yield_gap_score_capped_at_one():
    state = RiaState()
    state.signals.append(
        _signal(
            "dex:2",
            SignalType.YIELD_GAP,
            {"totalValueLockedUSD": 100.0, "cumulativeVolumeUSD": 10_000.0},
        )
    )

    await run_scout(state)

    assert state.ranked[0]["rank_score"] == 1.0


async def test_liquidation_proximity_scored_by_utilization():
    state = RiaState()
    state.signals.append(
        _signal(
            "lending:1",
            SignalType.LIQUIDATION_PROXIMITY,
            {"utilization": 0.92},
        )
    )

    await run_scout(state)

    assert state.ranked[0]["rank_score"] == 0.92


async def test_rate_divergence_scored_by_distance_from_neutral_band():
    state = RiaState()
    state.signals.append(
        _signal(
            "lending:2",
            SignalType.RATE_DIVERGENCE,
            {"utilization": 0.2},
        )
    )

    await run_scout(state)

    # abs(0.2 - 0.5) * 2 = 0.6
    assert state.ranked[0]["rank_score"] == pytest.approx(0.6)


async def test_unknown_signal_type_uses_fallback_score():
    state = RiaState()
    state.signals.append(
        _signal("pool:1", SignalType.POOL_IMBALANCE, {"anything": 1})
    )

    await run_scout(state)

    assert state.ranked[0]["rank_score"] == 0.5


async def test_run_scout_does_not_double_rank_existing_signals():
    state = RiaState()
    signal = _signal(
        "dex:3",
        SignalType.YIELD_GAP,
        {"totalValueLockedUSD": 100.0, "cumulativeVolumeUSD": 100.0},
    )
    state.signals.append(signal)

    await run_scout(state)
    await run_scout(state)

    assert len(state.ranked) == 1


async def test_run_scout_sorts_new_rankings_by_score_descending():
    state = RiaState()
    state.signals.append(
        _signal(
            "lending:low",
            SignalType.LIQUIDATION_PROXIMITY,
            {"utilization": 0.3},
        )
    )
    state.signals.append(
        _signal(
            "lending:high",
            SignalType.LIQUIDATION_PROXIMITY,
            {"utilization": 0.95},
        )
    )

    await run_scout(state)

    assert [r["signal"]["id"] for r in state.ranked] == ["lending:high", "lending:low"]
