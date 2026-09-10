"""ORACLE — external signal enrichment, paid via the x402-gated MCP server.

Containment rule: ORACLE is the *only* agent with HBAR payment authority.
This module is the sole caller of `hedera.x402_client.X402Client` from
inside the pipeline — RECON, SCOUT, RISK, EXEC, AUDIT must never import it.

For every `RiskAssessment` RISK flagged `above_threshold` and not yet
enriched, ORACLE calls the MCP server's `get_risk_score` tool (the "main
SKU" per README's Priced Tools table) and appends the result to
`state.enrichments`, in the exact shape `agents/exec.py` already documents
and consumes:

    {
        "signal_id": str, "tool": str, "confidence_delta": float,
        "hbar_cost": float, "tx_id": str, "enriched_at": str,
    }

Budget discipline: `state.budget_hbar` is a hard ceiling for the whole run,
not per-call. Before paying for any one enrichment, ORACLE checks
`state.remaining_budget()` covers that tool's price; if not, it stops
enriching for this cycle (logs why) rather than partially spending past the
operator's configured budget. A payment failure for one signal doesn't stop
the others — it's logged and that signal is simply left unenriched, so EXEC
correctly leaves it undispatched (see exec.py's gating).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from hedera.wallet import HederaWallet, WalletConfigError
from hedera.x402_client import X402Client, X402PaymentError
from mcp_server.pricing import TOOL_PRICES
from pipeline.state import RiaState, RiskAssessment, now_iso

logger = logging.getLogger("ria.oracle")

ENRICHMENT_TOOL = "get_risk_score"
DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"


def _client_from_env() -> X402Client:
    wallet = HederaWallet.from_env()
    mcp_url = os.environ.get("MCP_SERVER_URL", DEFAULT_MCP_URL)
    return X402Client(wallet=wallet, mcp_url=mcp_url)


def _signal_id(assessment: RiskAssessment) -> str:
    return assessment["opportunity"]["signal"]["id"]


async def _enrich_one(
    assessment: RiskAssessment, client: X402Client
) -> dict[str, Any] | None:
    signal = assessment["opportunity"]["signal"]
    try:
        outcome = await client.call_tool(ENRICHMENT_TOOL, {"opportunity": signal})
    except X402PaymentError as exc:
        logger.warning("ORACLE: enrichment failed for %s: %s", signal["id"], exc)
        return None

    tx_id = None
    if outcome.settlement:
        tx_id = outcome.settlement.get("transactionId") or outcome.settlement.get("transaction")

    return {
        "signal_id": signal["id"],
        "tool": ENRICHMENT_TOOL,
        "confidence_delta": outcome.result.get("confidence_delta", 0.0),
        "hbar_cost": outcome.hbar_paid,
        "tx_id": tx_id,
        "enriched_at": now_iso(),
        "raw_response": outcome.result.get("raw_response"),
    }


async def run_oracle(state: RiaState, client: X402Client | None = None) -> RiaState:
    """Pay to enrich every above-threshold, not-yet-enriched assessment.

    `client` lets callers (tests, or a runner with an explicit wallet) inject
    an X402Client instead of ORACLE resolving one from HEDERA_ACCOUNT_ID /
    HEDERA_PRIVATE_KEY / MCP_SERVER_URL at call time.
    """
    already_enriched_ids = {e["signal_id"] for e in state.enrichments}
    to_enrich = [
        a
        for a in state.assessments
        if a["above_threshold"] and _signal_id(a) not in already_enriched_ids
    ]
    if not to_enrich:
        return state

    try:
        client = client or _client_from_env()
    except WalletConfigError as exc:
        logger.warning("ORACLE: no wallet configured, skipping enrichment this cycle: %s", exc)
        return state

    price_hbar = TOOL_PRICES[ENRICHMENT_TOOL].price_hbar

    for assessment in to_enrich:
        if state.remaining_budget() < price_hbar:
            logger.warning(
                "ORACLE: remaining budget %.4f HBAR < %.4f HBAR price — stopping enrichment "
                "for this cycle (%d assessment(s) left unenriched)",
                state.remaining_budget(), price_hbar, len(to_enrich) - to_enrich.index(assessment),
            )
            break

        enrichment = await _enrich_one(assessment, client)
        if enrichment is not None:
            state.enrichments.append(enrichment)
            state.hbar_spent += enrichment["hbar_cost"]

    logger.info(
        "ORACLE: enriched %d/%d assessment(s), %.4f HBAR spent this run (%.4f remaining)",
        len(state.enrichments) - len(already_enriched_ids), len(to_enrich),
        state.hbar_spent, state.remaining_budget(),
    )
    return state
