"""`stream_liquidation_alerts(protocol, threshold)` — 0.001 HBAR / alert.

Data source: Substreams, processed and normalized — see README.md >
"Priced tools" and "Layer 1 — The Graph, Free & Load-Bearing". The raw
Substreams feed is RECON's territory (`graph/substreams_client.py`, Layer 1,
free); this tool is the paid, filtered, agent-ready product built on top of
it — it does not re-implement Substreams ingestion.

`graph/substreams_client.py` doesn't exist in this repo yet (still 🔜 per
the target repo structure), so this module imports it lazily and fails
loud with a clear message rather than fabricating alert data.

Billing note: pricing.py prices this tool per *alert*, not per call, which
the x402 middleware doesn't yet meter individually (it gates the call, not
each alert in the response) — see mcp_server/x402_middleware.py's docstring
for the same caveat. Good enough for a single-payment demo; a follow-up
would settle one x402 payment per alert delivered.
"""

from __future__ import annotations

from typing import Any


class LiquidationStreamError(RuntimeError):
    """Raised when the underlying Substreams client isn't available/wired."""


async def stream_liquidation_alerts(
    protocol: str, threshold: float = 0.8, limit: int = 10
) -> dict[str, Any]:
    """Pre-filtered liquidation-proximity alerts for `protocol`.

    `threshold` is the minimum liquidation-proximity score (0-1) an alert
    must clear to be included; `limit` caps how many alerts one call
    returns (each billed at 0.001 HBAR per `mcp_server.pricing`).
    """
    try:
        from graph.substreams_client import SubstreamsClient  # type: ignore[import-not-found]
    except ImportError as exc:
        raise LiquidationStreamError(
            "graph.substreams_client is not available yet — this tool "
            "depends on RECON's Substreams client (README.md > Repository "
            "Structure marks it 🔜). Not implemented here by design: Layer 1 "
            "data ingestion is out of scope for mcp_server/."
        ) from exc

    client = SubstreamsClient.from_env()
    alerts = await client.liquidation_alerts(protocol=protocol, threshold=threshold, limit=limit)
    return {"protocol": protocol, "threshold": threshold, "alerts": alerts, "count": len(alerts)}
