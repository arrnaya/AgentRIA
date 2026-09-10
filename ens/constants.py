"""Fixed ENS identity table + on-chain constants for RIA's Sepolia layer.

The subname table below is deliberately fixed by README.md > "Layer 3 —
Identity & Visibility" > "ENSv2 agent identity (Sepolia)": 4 agents
(RECON, ORACLE, EXEC, AUDIT), not 6 — SCOUT and RISK are internal-only and
never externally addressed, so they don't get subnames. Don't add entries
here without updating that README table, the dashboard's identity panel
(`src/app/app/page.tsx`), and the checklist in lockstep — see
.claude/agents/ens-identity-engineer.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

PARENT_NAME = "agentria.eth"

# ENSIP-26 text record keys. "version" and "capabilities" are free-form per
# the README table; AUDIT additionally carries "hcs-topic-id" once the
# Hedera lane (hedera-payments-engineer, hedera/hcs_logger.py) creates its
# HCS topic — until then it's populated with a clearly-labeled placeholder.
KEY_ENDPOINT = "endpoint"
KEY_VERSION = "version"
KEY_CAPABILITIES = "capabilities"
KEY_HCS_TOPIC_ID = "hcs-topic-id"

PROTOCOL_VERSION = os.environ.get("RIA_AGENT_PROTOCOL_VERSION", "1.0.0")

# Placeholder until mcp_server/ (owned by hedera-payments-engineer) ships a
# real HTTP/SSE endpoint per agent. Overridable per-agent via
# RIA_<AGENT>_ENDPOINT so this can be flipped to a live URL without a code
# change once that lane lands.
_DASHBOARD_ORIGIN = "https://ria-agent.vercel.app"


@dataclass(frozen=True)
class AgentIdentity:
    """One row of the fixed subname table."""

    agent_id: str  # short id used across the codebase, e.g. "oracle"
    label: str  # ENS label, e.g. "oracle" -> oracle.agentria.eth
    capabilities: str
    extra_records: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.label}.{PARENT_NAME}"

    def endpoint_env_var(self) -> str:
        return f"RIA_{self.agent_id.upper()}_ENDPOINT"

    def endpoint(self) -> str:
        default = f"{_DASHBOARD_ORIGIN}/agents/{self.agent_id}"
        return os.environ.get(self.endpoint_env_var(), default)

    def text_records(self) -> dict[str, str]:
        records = {
            KEY_ENDPOINT: self.endpoint(),
            KEY_VERSION: PROTOCOL_VERSION,
            KEY_CAPABILITIES: self.capabilities,
        }
        records.update(self.extra_records)
        return records


# hcs-topic-id is set once AUDIT's HCS topic exists (hedera/hcs_logger.py).
# RIA_AUDIT_HCS_TOPIC_ID lets register.py pick up the real value without
# this file needing an edit when that lane lands.
_AUDIT_HCS_TOPIC_ID = os.environ.get("RIA_AUDIT_HCS_TOPIC_ID", "pending-hcs-topic")

SUBNAME_TABLE: dict[str, AgentIdentity] = {
    identity.agent_id: identity
    for identity in (
        AgentIdentity("recon", "recon", "data-ingestion"),
        AgentIdentity("oracle", "oracle", "enrichment+payment"),
        AgentIdentity("exec", "exec", "execution-gating"),
        AgentIdentity(
            "audit",
            "audit",
            "audit-logging",
            extra_records={KEY_HCS_TOPIC_ID: _AUDIT_HCS_TOPIC_ID},
        ),
    )
}

# --- On-chain constants -----------------------------------------------
#
# ENSRegistry and PublicResolver addresses below are verified directly
# against ensdomains/ens-contracts (deployments/sepolia/*.json, chainId
# 11155111) — these are ENSv1-era contracts that are still live on Sepolia
# today and implement the exact node-scoped `approve` / `isApprovedFor`
# access-control model that ENSv2 documents describe as its "Permissioned
# Resolver" / "Enhanced Access Control" (per-record, per-node delegate
# approval rather than a single shared operator). ENSv2 deploys a fresh
# Permissioned Resolver proxy per name *owner* (via its Verifiable
# Factory), so there is no single fixed address to hardcode for
# `agentria.eth` — set ENS_RESOLVER_ADDRESS once you know it (check
# https://sepolia.app.ens.domains/agentria.eth or docs.ens.domains/learn/deployments
# for the current one) and this module resolves to it; PublicResolver
# below is the safe, well-tested fallback default so the live script has
# somewhere real to point at even before that address is confirmed.
ENS_REGISTRY_ADDRESS = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"
DEFAULT_PUBLIC_RESOLVER_ADDRESS = "0xE99638b40E4Fff0129D56f03b55b6bbC4BBE49b5"

SEPOLIA_CHAIN_ID = 11155111

# The exact function signatures RIA calls (used by ens/abi.py's Function
# helper to build calldata) are verified directly against the real,
# currently-deployed contract source — contracts/registry/ENSRegistry.sol
# and contracts/resolvers/PublicResolver.sol in ensdomains/ens-contracts —
# and defined alongside their call sites in ens/register.py and
# ens/resolver.py rather than duplicated here.
