"""EXEC — gate and dispatch actions.

EXEC is the last agent before AUDIT. It never pays HBAR itself — per
README's containment rule, ORACLE is the *only* agent with payment
authority, so a reasoning error here can never drain the wallet. EXEC only
reads what ORACLE already paid for and decides whether to dispatch.

## Assumed ORACLE enrichment shape

ORACLE is being built in parallel (`hedera-payments-engineer`) and may not
exist yet in this tree. EXEC codes against a documented shape for
`state.enrichments` entries so the other lane has a concrete contract to
conform to — this is *not* discovered from ORACLE's code, it's the
interface EXEC needs and assumes:

    {
        "signal_id": str,           # ties back to OpportunitySignal["id"]
        "tool": str,                # MCP tool called, e.g. "get_risk_score"
        "confidence_delta": float,  # adjustment to RISK's confidence, +/-
        "hbar_cost": float,         # HBAR paid for this one enrichment call
        "tx_id": str,               # Hedera tx id for the x402 payment
        "enriched_at": str,         # ISO 8601 timestamp
    }

If ORACLE's real output shape differs, only `_find_enrichment` and the
`confidence_delta` read in `gate_and_dispatch` need to change — everything
else is agnostic to it.

## Gating logic

EXEC dispatches an action for a `RiskAssessment` only if *all* of:

1. RISK already flagged it `above_threshold` (RISK's own gate).
2. An ORACLE enrichment exists for that signal — no enrichment means
   ORACLE hasn't priced/confirmed it yet, so EXEC waits rather than acting
   on a stale RISK-only confidence number.
3. `assessment.confidence + enrichment.confidence_delta` is *still* >=
   `state.risk_threshold` — ORACLE's paid enrichment can downgrade a
   signal RISK liked, and EXEC honors that.

Anything that doesn't clear all three is left out of `state.actions`
entirely (not written as a rejected/alert record) — the RISK -> alert-queue
routing decision already happened one hop earlier, in the StateGraph's
conditional edge, before EXEC ever runs. EXEC is not itself a router.

Each signal is dispatched at most once: EXEC skips any signal id already
present in `state.actions`.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.state import RiaState, RiskAssessment, now_iso

logger = logging.getLogger("ria.exec")


def _find_enrichment(
    signal_id: str, enrichments: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for enrichment in enrichments:
        if enrichment.get("signal_id") == signal_id:
            return enrichment
    return None


def gate_and_dispatch(
    assessment: RiskAssessment,
    enrichments: list[dict[str, Any]],
    risk_threshold: float,
) -> dict[str, Any] | None:
    """Return an action dict if this assessment clears every gate, else None."""
    if not assessment["above_threshold"]:
        return None

    signal = assessment["opportunity"]["signal"]
    enrichment = _find_enrichment(signal["id"], enrichments)
    if enrichment is None:
        logger.info("EXEC: %s above threshold but no ORACLE enrichment yet — waiting", signal["id"])
        return None

    final_confidence = assessment["confidence"] + enrichment.get("confidence_delta", 0.0)
    if final_confidence < risk_threshold:
        logger.info(
            "EXEC: %s downgraded by ORACLE enrichment to %.3f, below %.2f threshold — skipped",
            signal["id"], final_confidence, risk_threshold,
        )
        return None

    return {
        "signal_id": signal["id"],
        "protocol": signal["protocol"],
        "network": signal["network"],
        "type": signal["type"],
        "position_size_usd": assessment["position_size_usd"],
        "confidence": final_confidence,
        "enrichment_tool": enrichment.get("tool"),
        "enrichment_tx_id": enrichment.get("tx_id"),
        "status": "dispatched",
        "dispatched_at": now_iso(),
    }


async def run_exec(state: RiaState) -> RiaState:
    """Gate every not-yet-dispatched assessment against ORACLE's enrichment
    and the risk threshold, appending dispatched actions to state.actions."""
    already_dispatched_ids = {a["signal_id"] for a in state.actions}

    new_actions: list[dict[str, Any]] = []
    for assessment in state.assessments:
        signal_id = assessment["opportunity"]["signal"]["id"]
        if signal_id in already_dispatched_ids:
            continue
        action = gate_and_dispatch(assessment, state.enrichments, state.risk_threshold)
        if action is not None:
            new_actions.append(action)

    logger.info("EXEC: dispatched %d actions", len(new_actions))
    state.actions.extend(new_actions)
    return state
