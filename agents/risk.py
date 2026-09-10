"""RISK — confidence scoring and position sizing.

RISK turns SCOUT's raw `rank_score` into a `confidence` RISK is willing to
stand behind, and a conservative `position_size_usd`. Like SCOUT, this is a
simple, fully explainable heuristic — not a model:

- **Confidence** discounts `rank_score` by a liquidity factor: a signal
  sitting on top of a deep pool/market is less likely to be noise or a
  stale/manipulated read than the same raw score on a shallow one.
  ``liquidity_factor = min(liquidity_usd / LIQUIDITY_REFERENCE_USD, 1.0)``
  ``confidence = rank_score * liquidity_factor``
  where `liquidity_usd` is the pool's TVL for DEX signals or the market's
  total deposits for lending signals (whichever `raw_metrics` key is
  present), and `LIQUIDITY_REFERENCE_USD` (2,000,000) is the round,
  documented size treated as "large enough to fully trust."

- **Position size** never recommends more than a fixed share of the
  underlying pool/market's own liquidity — sizing a position past that
  risks moving the market itself, independent of how confident RISK is —
  and is then scaled down further by `confidence`:
  ``position_size_usd = confidence * min(liquidity_usd * MAX_LIQUIDITY_SHARE, MAX_POSITION_USD)``
  `MAX_LIQUIDITY_SHARE` (1%) and `MAX_POSITION_USD` ($50,000) are both
  round, conservative caps for a hackathon-scale demo — not a real
  portfolio-sizing model.

- **above_threshold** is a direct comparison: ``confidence >=
  state.risk_threshold`` (default 0.65, operator-configurable). This is the
  value the StateGraph's conditional edge reads to route toward
  ORACLE/EXEC vs. the human alert queue — RISK only computes it here, it
  does not route.

Every ranked opportunity is assessed exactly once: RISK skips any signal id
already present in `state.assessments`.
"""

from __future__ import annotations

import logging

from pipeline.state import OpportunitySignal, RankedOpportunity, RiaState, RiskAssessment

logger = logging.getLogger("ria.risk")

# Liquidity (USD) treated as "large enough to fully trust" a signal.
LIQUIDITY_REFERENCE_USD = 2_000_000.0

# Never recommend sizing a position above this share of the underlying
# pool/market's own liquidity, regardless of confidence.
MAX_LIQUIDITY_SHARE = 0.01

# Hard ceiling on any single recommended position, independent of liquidity.
MAX_POSITION_USD = 50_000.0


def _liquidity_usd(signal: OpportunitySignal) -> float:
    metrics = signal["raw_metrics"]
    return metrics.get("totalValueLockedUSD") or metrics.get("totalDepositBalanceUSD") or 0.0


def score_confidence(ranked: RankedOpportunity) -> float:
    liquidity_usd = _liquidity_usd(ranked["signal"])
    liquidity_factor = min(liquidity_usd / LIQUIDITY_REFERENCE_USD, 1.0)
    return ranked["rank_score"] * liquidity_factor


def size_position(ranked: RankedOpportunity, confidence: float) -> float:
    liquidity_usd = _liquidity_usd(ranked["signal"])
    liquidity_cap = min(liquidity_usd * MAX_LIQUIDITY_SHARE, MAX_POSITION_USD)
    return confidence * liquidity_cap


def assess(ranked: RankedOpportunity, risk_threshold: float) -> RiskAssessment:
    confidence = score_confidence(ranked)
    position_size_usd = size_position(ranked, confidence)
    return RiskAssessment(
        opportunity=ranked,
        confidence=confidence,
        position_size_usd=position_size_usd,
        above_threshold=confidence >= risk_threshold,
    )


async def run_risk(state: RiaState) -> RiaState:
    """Score every not-yet-assessed ranked opportunity and append the result."""
    already_assessed_ids = {
        a["opportunity"]["signal"]["id"] for a in state.assessments
    }
    new_assessments: list[RiskAssessment] = [
        assess(ranked, state.risk_threshold)
        for ranked in state.ranked
        if ranked["signal"]["id"] not in already_assessed_ids
    ]

    above = sum(1 for a in new_assessments if a["above_threshold"])
    logger.info(
        "RISK: assessed %d opportunities (%d above %.2f threshold)",
        len(new_assessments), above, state.risk_threshold,
    )
    state.assessments.extend(new_assessments)
    return state
