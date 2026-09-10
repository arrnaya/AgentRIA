"""RIA's WebSocket feed — fans out typed pipeline events to the dashboard.

The dashboard (`src/app/app/page.tsx`, `frontend-integrator`'s lane) is a
read-only observer: it never writes back, so `RiaWsServer` only ever sends.
Four event types, matching README's Layer 3 dashboard panel table:

    SIGNAL  -> Opportunities Feed  (emitted after SCOUT ranks a signal)
    TRACE   -> Agent Trace         (emitted after every StateGraph node)
    PAYMENT -> Payment Monitor     (emitted per ORACLE x402 payment)
    AUDIT   -> HCS Audit Trail     (emitted per AUDIT entry)

Every event on the wire is `{"event": <type>, "data": {...}, "ts": <iso>}`.
The `data` payload shapes below are deliberately kept close to the mock
arrays already in `src/app/app/page.tsx` (`opportunities`, `trace`) so
wiring the real feed in doesn't require a frontend rewrite — see each
builder function's docstring for the exact fields assumed on each side.

PAYMENT and AUDIT payloads read from ORACLE/AUDIT output whose real shape
isn't finalized in this tree yet (`hedera-payments-engineer`'s lane) — both
builders use defensive `.get()` reads against the documented assumed shapes
(see `agents/exec.py`'s ORACLE enrichment contract) rather than assuming
required keys, so a slightly different real shape degrades gracefully
instead of raising.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, broadcast, serve

from pipeline.state import OpportunitySignal, SignalType, now_iso

logger = logging.getLogger("ria.ws_server")

EVENT_TYPES = ("SIGNAL", "TRACE", "PAYMENT", "AUDIT")

# Human-readable labels matching src/app/app/page.tsx's mock `opportunities`
# array exactly (e.g. "Collateral ratio drift" for collateral_drift).
_TYPE_LABELS: dict[SignalType, str] = {
    SignalType.YIELD_GAP: "Yield gap",
    SignalType.LIQUIDATION_PROXIMITY: "Liquidation proximity",
    SignalType.RATE_DIVERGENCE: "Rate divergence",
    SignalType.POOL_IMBALANCE: "Pool imbalance",
    SignalType.COLLATERAL_DRIFT: "Collateral ratio drift",
}


def signal_payload(signal: OpportunitySignal, rank_score: float) -> dict[str, Any]:
    """SIGNAL event data — mirrors page.tsx's `opportunities` row shape
    (protocol, pair, type, confidence) plus network/observed_at for the
    trace/audit panels to cross-reference. Presentation-only fields the
    mock also carries (`time`, `tone`) are left to the frontend to derive
    client-side rather than encoded here."""
    return {
        "signal_id": signal["id"],
        "protocol": signal["protocol"],
        "network": signal["network"],
        "pair": signal["pair"],
        "type": signal["type"].value if isinstance(signal["type"], SignalType) else signal["type"],
        "type_label": _TYPE_LABELS.get(signal["type"], str(signal["type"])),
        "confidence": round(rank_score, 4),
        "observed_at": signal["observed_at"],
    }


def trace_payload(name: str, status: str, note: str) -> dict[str, Any]:
    """TRACE event data — exact shape of page.tsx's mock `trace` rows."""
    return {"name": name, "status": status, "note": note}


def payment_payload(enrichment: dict[str, Any]) -> dict[str, Any]:
    """PAYMENT event data for one ORACLE x402 call, read from an enrichment
    dict matching the assumed shape documented in agents/exec.py
    (signal_id, tool, hbar_cost, tx_id, ...)."""
    return {
        "signal_id": enrichment.get("signal_id"),
        "tool": enrichment.get("tool"),
        "amount_hbar": enrichment.get("hbar_cost"),
        "facilitator": "Blocky402",
        "tx_id": enrichment.get("tx_id"),
        "status": "confirmed" if enrichment.get("tx_id") else "pending",
    }


def audit_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """AUDIT event data for one HCS log entry. AUDIT's real output shape
    isn't finalized in this tree yet, so every field is read defensively."""
    return {
        "action": entry.get("action", "AUDIT"),
        "signal_id": entry.get("signal_id"),
        "hcs_topic_id": entry.get("hcs_topic_id"),
        "tx_id": entry.get("tx_id"),
        "note": entry.get("note", ""),
        "logged_at": entry.get("logged_at", now_iso()),
    }


class RiaWsServer:
    """Minimal fan-out WebSocket server: one `emit()` call reaches every
    currently-connected dashboard client. Inbound messages are ignored —
    the dashboard never writes back."""

    def __init__(self, host: str = "0.0.0.0", port: int = 3001) -> None:
        self.host = host
        self.port = port
        self._server: Server | None = None
        self._clients: set[ServerConnection] = set()

    @property
    def bound_port(self) -> int | None:
        """The actual listening port (useful when constructed with port=0)."""
        if self._server is None:
            return None
        return self._server.sockets[0].getsockname()[1]

    async def _handler(self, connection: ServerConnection) -> None:
        self._clients.add(connection)
        logger.info("WS client connected (%d total)", len(self._clients))
        try:
            async for _ in connection:
                pass
        finally:
            self._clients.discard(connection)
            logger.info("WS client disconnected (%d total)", len(self._clients))

    async def start(self) -> None:
        self._server = await serve(self._handler, self.host, self.port)
        logger.info("RIA WebSocket server listening on ws://%s:%d", self.host, self.bound_port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Fan out one typed event to every connected client.

        A no-op with zero clients connected — the pipeline should never
        block or error just because no dashboard is watching yet.
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown WS event type: {event_type!r}. Expected one of {EVENT_TYPES}")
        if not self._clients:
            return
        message = json.dumps({"event": event_type, "data": data, "ts": now_iso()})
        broadcast(self._clients, message)
