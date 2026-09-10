"""AUDIT — post-execution logging to the Hedera Consensus Service.

Per README.md > "x402 Payment Flow — Step by Step" (step 8): after every
EXEC action, log tool name, HBAR amount, Hedera tx ID, and a response hash
to an HCS topic — a tamper-proof, block-timestamped record the dashboard's
HCS Audit Trail panel and judges' HashScan/mirror-node checks both read.

Not a payment-authority module (see hedera/hcs_logger.py's docstring):
submitting an HCS message costs a small fixed network fee, distinct from
ORACLE's commercial x402 payment. This module never imports
`hedera.wallet.HederaWallet` or `hedera.x402_client`.

Each dispatched action in `state.actions` is logged at most once: AUDIT
skips any signal id already present in `state.audit_entries`.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from hedera.hcs_logger import HcsConfigError, HcsLogger, HcsSubmitError
from pipeline.state import RiaState, now_iso

logger = logging.getLogger("ria.audit")


def _find_enrichment(signal_id: str, enrichments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for enrichment in enrichments:
        if enrichment.get("signal_id") == signal_id:
            return enrichment
    return None


def _response_hash(enrichment: dict[str, Any] | None) -> str | None:
    if enrichment is None:
        return None
    raw = enrichment.get("raw_response")
    if raw is None:
        return None
    return hashlib.sha256(str(raw).encode()).hexdigest()


async def run_audit(state: RiaState, logger_client: HcsLogger | None = None) -> RiaState:
    """Log every not-yet-audited dispatched action to HCS.

    `logger_client` lets callers (tests, or a runner with an explicit
    topic) inject an HcsLogger instead of AUDIT resolving one from
    HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY / HCS_TOPIC_ID at call time.
    """
    already_audited_ids = {e.get("signal_id") for e in state.audit_entries}
    to_audit = [a for a in state.actions if a["signal_id"] not in already_audited_ids]
    if not to_audit:
        return state

    try:
        hcs = logger_client or HcsLogger.from_env()
    except HcsConfigError as exc:
        logger.warning("AUDIT: no HCS topic configured, skipping logging this cycle: %s", exc)
        return state

    for action in to_audit:
        enrichment = _find_enrichment(action["signal_id"], state.enrichments)
        try:
            receipt = hcs.log_payment(
                tool_name=(enrichment or {}).get("tool", "unknown"),
                hbar_amount=(enrichment or {}).get("hbar_cost", 0.0),
                hedera_tx_id=(enrichment or {}).get("tx_id") or "",
                response_hash=_response_hash(enrichment),
            )
        except HcsSubmitError as exc:
            logger.warning("AUDIT: failed to log %s to HCS: %s", action["signal_id"], exc)
            continue

        state.audit_entries.append(
            {
                "signal_id": action["signal_id"],
                "action": "EXEC_DISPATCHED",
                "hcs_topic_id": receipt["topic_id"],
                "tx_id": receipt["consensus_tx_id"],
                "content_hash": receipt.get("content_hash"),
                "logged_at": now_iso(),
                "note": f"{action['protocol']} {action['type']} dispatched, logged to HCS",
            }
        )

    logger.info("AUDIT: logged %d/%d action(s) to HCS", len(state.audit_entries) - len(already_audited_ids), len(to_audit))
    return state
