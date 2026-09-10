"""The RIA LangGraph `StateGraph` — wires all six agents into one pipeline.

    START -> RECON -> SCOUT -> RISK -> (conditional) -> EXEC -> AUDIT -> END
                                   |
                        above_threshold?  ---- yes ----> ORACLE -> EXEC
                                   `------- no --------> ALERT  -> EXEC

RISK's conditional edge decides, per run, whether any assessment cleared
`state.risk_threshold`. If at least one did, the graph calls ORACLE to pay
for enrichment before EXEC gates and dispatches. If none did, the graph
skips straight to a no-op ALERT node (logging only — the dashboard's job to
render the human alert queue, not this module's) so no HBAR is spent on a
cycle with nothing worth enriching. Both branches converge on EXEC, which
re-applies its own per-signal gates regardless of which branch ran (see
`agents/exec.py`) — the graph-level branch is a cost/tracing optimization,
not the only safety gate.

## ORACLE / AUDIT stubs

ORACLE and AUDIT are owned by `hedera-payments-engineer` and may not exist
yet in this tree (`agents/oracle.py`, `agents/audit.py`). This module
imports them if present and falls back to a logging no-op stub otherwise,
so the graph runs end-to-end today against partially-stubbed downstream
agents rather than blocking on the other lane. Once those modules land,
this file picks them up automatically — nothing here needs to change. A
stub ORACLE passes `state` through with zero new `state.enrichments`
(spends no HBAR, per the containment rule that only ORACLE may pay); a
stub AUDIT passes `state` through with zero new `state.audit_entries`.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.exec import run_exec
from agents.recon import run_recon
from agents.risk import run_risk
from agents.scout import run_scout
from graph.subgraph_client import SubgraphClient
from pipeline.state import RiaState

logger = logging.getLogger("ria.graph")

try:
    from agents.oracle import run_oracle  # type: ignore[import-not-found]
except ImportError:

    async def run_oracle(state: RiaState) -> RiaState:  # type: ignore[misc]
        """Stub — agents/oracle.py not present yet (hedera-payments-engineer's
        lane). Pays no HBAR, adds no enrichments, just passes state through
        so the rest of the graph still runs end-to-end."""
        logger.warning(
            "ORACLE stub in use (agents/oracle.py not found) — "
            "passing %d above-threshold assessment(s) through unenriched",
            sum(1 for a in state.assessments if a["above_threshold"]),
        )
        return state


try:
    from agents.audit import run_audit  # type: ignore[import-not-found]
except ImportError:

    async def run_audit(state: RiaState) -> RiaState:  # type: ignore[misc]
        """Stub — agents/audit.py not present yet (hedera-payments-engineer's
        lane). Writes no HCS entries, just passes state through."""
        logger.warning(
            "AUDIT stub in use (agents/audit.py not found) — "
            "%d action(s) from this run were not logged to HCS",
            len(state.actions),
        )
        return state


async def run_alert(state: RiaState) -> RiaState:
    """No-op branch for a cycle where nothing cleared the risk threshold.

    Only logs — the human alert queue itself is rendered by the dashboard
    from the assessments already in state, not built here.
    """
    below = [a for a in state.assessments if not a["above_threshold"]]
    logger.info("ALERT: %d assessment(s) below threshold, routed to human alert queue", len(below))
    return state


def route_after_risk(state: RiaState) -> str:
    """Send the run toward ORACLE if any assessment cleared the threshold,
    otherwise skip enrichment entirely and go straight to the alert no-op.
    """
    if any(a["above_threshold"] for a in state.assessments):
        return "oracle"
    return "alert"


def build_graph(recon_client: SubgraphClient | None = None) -> CompiledStateGraph:
    """Assemble and compile the RIA StateGraph.

    `recon_client` lets callers (tests, or a runner with an explicit
    SubgraphClient) inject a client instead of RECON resolving one from
    `GRAPH_API_KEY` at call time.
    """

    async def _recon_node(state: RiaState) -> RiaState:
        return await run_recon(state, client=recon_client)

    g: StateGraph = StateGraph(RiaState)
    g.add_node("recon", _recon_node)
    g.add_node("scout", run_scout)
    g.add_node("risk", run_risk)
    g.add_node("oracle", run_oracle)
    g.add_node("alert", run_alert)
    g.add_node("exec", run_exec)
    g.add_node("audit", run_audit)

    g.add_edge(START, "recon")
    g.add_edge("recon", "scout")
    g.add_edge("scout", "risk")
    g.add_conditional_edges("risk", route_after_risk, {"oracle": "oracle", "alert": "alert"})
    g.add_edge("oracle", "exec")
    g.add_edge("alert", "exec")
    g.add_edge("exec", "audit")
    g.add_edge("audit", END)

    return g.compile()


async def run_pipeline(
    state: RiaState, recon_client: SubgraphClient | None = None
) -> RiaState:
    """Run one full pipeline cycle and return the resulting RiaState.

    LangGraph's `ainvoke` returns a plain dict of the state's fields (not
    the dataclass instance) — this reconstructs a `RiaState` so callers
    (the runner, the WebSocket server) get the same typed object and
    methods (`remaining_budget()`) they passed in.
    """
    compiled = build_graph(recon_client=recon_client)
    result = await compiled.ainvoke(state)
    return RiaState(**result)
