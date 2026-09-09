"""Typed state that flows through every agent in the LangGraph StateGraph.

One `RiaState` instance is threaded through RECON -> SCOUT -> RISK -> ORACLE
-> EXEC -> AUDIT. Each agent reads what it needs and appends to the shared
lists rather than mutating prior agents' output, so the full trace survives
to the end of the run for AUDIT and the dashboard WebSocket feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict


class SignalType(str, Enum):
    YIELD_GAP = "yield_gap"
    LIQUIDATION_PROXIMITY = "liquidation_proximity"
    RATE_DIVERGENCE = "rate_divergence"
    POOL_IMBALANCE = "pool_imbalance"
    COLLATERAL_DRIFT = "collateral_drift"


class OpportunitySignal(TypedDict):
    """One normalized signal produced by RECON from raw Graph data."""

    id: str
    protocol: str
    network: str
    pair: str
    type: SignalType
    raw_metrics: dict[str, Any]
    source: str
    observed_at: str


class RankedOpportunity(TypedDict):
    """A signal after SCOUT has scored it for raw potential."""

    signal: OpportunitySignal
    rank_score: float


class RiskAssessment(TypedDict):
    """A ranked opportunity after RISK has sized and scored it."""

    opportunity: RankedOpportunity
    confidence: float
    position_size_usd: float
    above_threshold: bool


@dataclass
class RiaState:
    """Shared state object threaded through the StateGraph.

    risk_threshold and budget_hbar are the two knobs an operator sets before
    a run; everything else accumulates as agents execute.
    """

    risk_threshold: float = 0.65
    budget_hbar: float = 10.0

    signals: list[OpportunitySignal] = field(default_factory=list)
    ranked: list[RankedOpportunity] = field(default_factory=list)
    assessments: list[RiskAssessment] = field(default_factory=list)
    enrichments: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    audit_entries: list[dict[str, Any]] = field(default_factory=list)

    hbar_spent: float = 0.0

    def remaining_budget(self) -> float:
        return max(0.0, self.budget_hbar - self.hbar_spent)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
