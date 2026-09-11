"""pipeline/runner.py — CLI entrypoint for the RIA LangGraph pipeline.

Starts the WebSocket feed (`pipeline/ws_server.py`) and then repeatedly
runs one full StateGraph cycle (`pipeline/graph.py`) every `--interval`
seconds, streaming a TRACE event as each node completes plus a
SIGNAL/PAYMENT/AUDIT event for whatever that node newly produced. Flag
names match README.md > "Running Locally" exactly:

    python pipeline/runner.py \\
      --mode live --networks ethereum,arbitrum,polygon \\
      --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3001 \\
      --mcp-server http://localhost:8080

Two flags are parsed but not fully wired to real behavior yet, and both
log a warning rather than silently no-op:

- `--networks`: only `ethereum` is wired end-to-end (`agents/recon.py`'s
  `DEX_SOURCES`/`LENDING_SOURCES`); other requested networks are logged
  and ignored.
- `--mode`: only `live` is implemented; there is no mock/demo data path
  (matching RECON's zero-mocked-data standard) so any other value still
  runs the live pipeline, with a warning that the mode itself isn't
  distinct yet.

`--mcp-server` sets `MCP_SERVER_URL` for the process (`agents/oracle.py`
reads it to build ORACLE's `X402Client`) -- defaults to
`http://127.0.0.1:8000/mcp` if omitted, matching `mcp_server/server.py`'s
own bind default, so a locally-run MCP server needs no flag at all.

A real run needs `GRAPH_API_KEY` set (RECON fails loud without it, by
design — see `graph/subgraph_client.py`).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

# README's "Running Locally" invokes this file directly (`python
# pipeline/runner.py ...`) rather than via `python -m`, which by default
# only puts pipeline/ (not the repo root) on sys.path and breaks the
# `pipeline.*` / `agents.*` absolute imports below. Insert the repo root
# unconditionally — harmless and idempotent when this module is instead
# imported normally (e.g. from the test suite, where pytest.ini already
# does the equivalent via `pythonpath = .`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.graph import build_graph
from pipeline.state import RiaState
from pipeline.ws_server import (
    RiaWsServer,
    audit_payload,
    payment_payload,
    signal_payload,
    trace_payload,
)

logger = logging.getLogger("ria.runner")

# Networks agents/recon.py is actually wired to today.
SUPPORTED_NETWORKS = {"ethereum"}

_NODE_LABELS = {
    "recon": "RECON",
    "scout": "SCOUT",
    "risk": "RISK",
    "oracle": "ORACLE",
    "alert": "ALERT",
    "exec": "EXEC",
    "audit": "AUDIT",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RIA LangGraph intelligence pipeline")
    parser.add_argument(
        "--mode", default="live", help="Run mode (only 'live' is implemented today)"
    )
    parser.add_argument(
        "--networks",
        default="ethereum",
        help="Comma-separated network list (only 'ethereum' is wired today)",
    )
    parser.add_argument("--risk-threshold", type=float, default=0.65, dest="risk_threshold")
    parser.add_argument("--budget-hbar", type=float, default=10.0, dest="budget_hbar")
    parser.add_argument(
        "--interval", type=int, default=30, help="Seconds between pipeline cycles"
    )
    parser.add_argument("--ws-port", type=int, default=3001, dest="ws_port")
    parser.add_argument(
        "--mcp-server",
        default=None,
        dest="mcp_server",
        help="x402-gated MCP server URL (consumed by ORACLE once it lands)",
    )
    return parser.parse_args(argv)


def _trace_for_node(node_name: str, values: dict, risk_threshold: float) -> tuple[str, str]:
    """Compute (status, note) for one TRACE event from a node's output."""
    if node_name == "recon":
        return (
            "Complete",
            f"Pulled {len(values.get('signals', []))} opportunity signal(s) from Subgraph Studio",
        )
    if node_name == "scout":
        return "Complete", f"Ranked {len(values.get('ranked', []))} signal(s)"
    if node_name == "risk":
        assessments = values.get("assessments", [])
        above = sum(1 for a in assessments if a["above_threshold"])
        return (
            f"{above}/{len(assessments)} above threshold",
            f"Risk threshold {risk_threshold:.2f}",
        )
    if node_name == "oracle":
        return "Complete", f"{len(values.get('enrichments', []))} enrichment(s) from ORACLE"
    if node_name == "alert":
        assessments = values.get("assessments", [])
        below = sum(1 for a in assessments if not a["above_threshold"])
        return "Routed -> human alert queue", f"{below} assessment(s) below threshold"
    if node_name == "exec":
        return "Complete", f"Dispatched {len(values.get('actions', []))} action(s)"
    if node_name == "audit":
        return "Complete", f"Logged {len(values.get('audit_entries', []))} entries to HCS"
    return "Complete", ""


async def run_cycle(state: RiaState, ws: RiaWsServer, recon_client=None) -> RiaState:
    """Run one full pipeline cycle, streaming TRACE/SIGNAL/PAYMENT/AUDIT
    events to `ws` as each StateGraph node completes.

    `recon_client` lets callers (tests, or a runner with an explicit
    SubgraphClient) inject a client instead of RECON resolving one from
    `GRAPH_API_KEY` at call time — see pipeline/graph.py's build_graph().
    """
    compiled = build_graph(recon_client=recon_client)
    values: dict = {}

    async for update in compiled.astream(state):
        node_name, node_values = next(iter(update.items()))
        values.update(node_values)

        status, note = _trace_for_node(node_name, node_values, state.risk_threshold)
        ws.emit(
            "TRACE",
            trace_payload(_NODE_LABELS.get(node_name, node_name.upper()), status, note),
        )

        if node_name == "scout":
            for ranked in node_values.get("ranked", []):
                ws.emit("SIGNAL", signal_payload(ranked["signal"], ranked["rank_score"]))
        elif node_name == "oracle":
            for enrichment in node_values.get("enrichments", []):
                ws.emit("PAYMENT", payment_payload(enrichment))
        elif node_name == "audit":
            for entry in node_values.get("audit_entries", []):
                ws.emit("AUDIT", audit_payload(entry))

    return RiaState(**values)


async def main_loop(args: argparse.Namespace, max_cycles: int | None = None) -> None:
    """Start the WS server and run pipeline cycles every `--interval`
    seconds. `max_cycles` (None = forever) exists so tests can run a
    bounded number of cycles instead of looping indefinitely.
    """
    if args.mode != "live":
        logger.warning(
            "--mode %s is not implemented yet; running the live pipeline anyway", args.mode
        )

    networks = [n.strip() for n in args.networks.split(",") if n.strip()]
    unsupported = [n for n in networks if n not in SUPPORTED_NETWORKS]
    if unsupported:
        logger.warning(
            "RECON is only wired to %s today; ignoring: %s",
            sorted(SUPPORTED_NETWORKS), unsupported,
        )

    if args.mcp_server:
        # agents/oracle.py now reads MCP_SERVER_URL (not this flag directly)
        # to build its X402Client -- wire it through here rather than
        # leaving `--mcp-server` a documented flag that silently does
        # nothing, which it was until ORACLE actually landed.
        os.environ["MCP_SERVER_URL"] = args.mcp_server
        logger.info("--mcp-server=%s -> MCP_SERVER_URL for ORACLE", args.mcp_server)

    ws = RiaWsServer(port=args.ws_port)
    await ws.start()
    logger.info(
        "RIA pipeline starting: risk_threshold=%.2f budget_hbar=%.2f interval=%ds",
        args.risk_threshold, args.budget_hbar, args.interval,
    )

    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            state = RiaState(risk_threshold=args.risk_threshold, budget_hbar=args.budget_hbar)
            try:
                await run_cycle(state, ws)
            except Exception:
                logger.exception("Pipeline cycle failed; will retry next interval")
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                await asyncio.sleep(args.interval)
    finally:
        await ws.stop()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    args = parse_args(argv)
    asyncio.run(main_loop(args))


if __name__ == "__main__":
    main()
