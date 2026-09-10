"""SCOUT — opportunity ranking.

SCOUT is the only agent that turns a raw `OpportunitySignal` into a
`rank_score` (0.0-1.0). It does not decide what's safe to act on — that's
RISK's job. The heuristic here is intentionally simple and fully explainable
per signal type, not a model:

- ``yield_gap``: capital efficiency, i.e. cumulative volume relative to TVL.
  A pool doing many multiples of its TVL in volume is earning outsized fees
  relative to capital at risk — that's "raw potential" in the yield sense.
  ``score = min(volume / tvl / YIELD_EFFICIENCY_CAP, 1.0)``.
- ``liquidation_proximity``: RECON already computes utilization for lending
  markets; SCOUT reuses it directly as urgency — a market pinned near full
  utilization is the one closest to a liquidation cascade, so
  ``score = min(utilization, 1.0)``.
- ``rate_divergence``: flagged by RECON for markets *not* near full
  utilization, where a rate quirk (rather than liquidation risk) is the more
  likely story. Scored by distance from a neutral 50% utilization band —
  the further utilization sits from "normal," the more likely a rate
  anomaly is present: ``score = min(abs(utilization - 0.5) * 2, 1.0)``.
- ``pool_imbalance`` / ``collateral_drift``: no RECON producer emits these
  yet (see agents/recon.py). SCOUT scores them at a fixed, conservative
  ``FALLBACK_SCORE`` rather than inventing a formula for data it has never
  seen — this is flagged loudly, not disguised as a real signal.

Each signal is scored exactly once: SCOUT skips any signal id already
present in ``state.ranked`` so re-running SCOUT on a state that already has
RECON's earlier output plus fresh signals doesn't double-rank.
"""

from __future__ import annotations

import logging

from pipeline.state import OpportunitySignal, RankedOpportunity, RiaState, SignalType

logger = logging.getLogger("ria.scout")

# Volume/TVL multiple treated as "maximum" capital efficiency for yield_gap
# scoring. Chosen as a round, explainable cap rather than fit to data.
YIELD_EFFICIENCY_CAP = 5.0

# Score assigned to signal types RECON does not currently emit
# (pool_imbalance, collateral_drift) — a neutral placeholder, not a claim.
FALLBACK_SCORE = 0.5


def _score_yield_gap(signal: OpportunitySignal) -> float:
    metrics = signal["raw_metrics"]
    tvl = metrics.get("totalValueLockedUSD", 0.0)
    volume = metrics.get("cumulativeVolumeUSD", 0.0)
    if tvl <= 0:
        return 0.0
    efficiency = volume / tvl
    return min(efficiency / YIELD_EFFICIENCY_CAP, 1.0)


def _score_liquidation_proximity(signal: OpportunitySignal) -> float:
    utilization = signal["raw_metrics"].get("utilization", 0.0)
    return min(max(utilization, 0.0), 1.0)


def _score_rate_divergence(signal: OpportunitySignal) -> float:
    utilization = signal["raw_metrics"].get("utilization", 0.0)
    return min(abs(utilization - 0.5) * 2, 1.0)


_SCORERS = {
    SignalType.YIELD_GAP: _score_yield_gap,
    SignalType.LIQUIDATION_PROXIMITY: _score_liquidation_proximity,
    SignalType.RATE_DIVERGENCE: _score_rate_divergence,
}


def rank_score(signal: OpportunitySignal) -> float:
    """Score one signal's raw potential, per the type-specific rules above."""
    scorer = _SCORERS.get(signal["type"])
    if scorer is None:
        logger.info(
            "SCOUT: no scorer for signal type %s (id=%s) — using fallback %.2f",
            signal["type"], signal["id"], FALLBACK_SCORE,
        )
        return FALLBACK_SCORE
    return scorer(signal)


async def run_scout(state: RiaState) -> RiaState:
    """Rank every not-yet-ranked signal in state.signals and append the result."""
    already_ranked_ids = {r["signal"]["id"] for r in state.ranked}
    new_rankings: list[RankedOpportunity] = [
        RankedOpportunity(signal=signal, rank_score=rank_score(signal))
        for signal in state.signals
        if signal["id"] not in already_ranked_ids
    ]
    new_rankings.sort(key=lambda r: r["rank_score"], reverse=True)

    logger.info("SCOUT: ranked %d new signals", len(new_rankings))
    state.ranked.extend(new_rankings)
    return state
