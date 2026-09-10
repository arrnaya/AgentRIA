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

# --- On-chain constants (ENSv2, standard Sepolia Beta deployment) ------
#
# ENSv2 replaces ENSv1's single flat ENSRegistry with "Hierarchical
# Registries" (docs.ens.domains/contracts/ensv2/overview): a name is a
# chain of entries across separate registry contract instances linked by
# subregistry pointers, and a name's resolver is looked up dynamically
# (it's whatever the current registry entry says, not a fixed address) --
# see ens/registry.py and ens/register.py's ensure_subregistry() /
# ensure_resolver(), which do exactly that lookup rather than hardcoding
# a resolver address here.
#
# IMPORTANT — there is more than one ENSv2 deployment on Sepolia.
# docs.ens.domains/learn/deployments lists a "Sepolia (ENSv2 Beta)"
# deployment; a separate ETHOnline-2026-hackathon-specific preview site
# (a "docs-bao.pages.dev" branch preview, not an ens.domains domain)
# claims a second, different "hackathon deployment" with different
# addresses and a different (older, no-per-node-scoping) resolver design.
# That second set was independently checked against the actual chain and
# rejected: a live, read-only `findOwner("agentria")` eth_call (selector
# 0x63560a8e, no ENS_PRIVATE_KEY needed) against
# https://ethereum-sepolia-rpc.publicnode.com returns the ZERO address on
# the hackathon-specific ETHRegistry (0x1d78834d97c1d7b1a38c1dedbd1a287cfed3971e)
# and a REAL, non-zero owner
# (0x6907187b9e63abf8eb5a8f956aa556f20be95a5f) on ENS_ETH_REGISTRY_ADDRESS
# below — i.e. `agentria.eth` lives on the standard ENSv2 Beta deployment,
# not the hackathon one. The addresses below are that standard
# deployment's, matching what the operator originally supplied and what
# docs.ens.domains/learn/deployments lists.
#
# ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS is additionally confirmed by
# reading its actual deployed *bytecode* (eth_getCode, same public RPC)
# and finding the real 4-byte selectors for setText, text,
# authorizeNameRoles, authorizeTextRoles, authorizeDataRoles,
# authorizeAddrRoles and grantRootRoles inside it — i.e. this isn't just
# "docs say this address", it's "the contract actually deployed here
# really does implement the functions this module calls." Those
# selectors are absent from the hackathon site's claimed
# "grantSetterRoles"-based design, which is a further reason that source
# was set aside for targeting purposes (see ens/resolver.py's module
# docstring for the isolation-mechanism detail).
ENS_ETH_REGISTRY_ADDRESS = "0xBDC85dD5b15D7ecb354cd7cb6f2c50b4f2c4F0E2"
ENS_VERIFIABLE_FACTORY_ADDRESS = "0x10dC6333CDFe1FCEf624c6e0a8221b91804Cd7ef"
ENS_USER_REGISTRY_IMPL_ADDRESS = "0x624a25d67B59D587752EbEc8DdeD8827dAe52050"
ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS = "0x9EAe5C2730a7dD16BDD1DeE6421a1B91e3B0365e"
# UpgradableUniversalResolverProxy — the DAO-managed, stable read-only
# entry point for ENSv2 name *resolution* (per docs.ens.domains/resolvers/universal:
# "an upgradable proxy... owned by the ENS DAO, so its address won't
# change... client frameworks default to the proxy so their libraries are
# future-proof"). It is confirmed read-only: it does not execute writes
# or modify state, so nothing in ens/register.py or ens/resolver.py ever
# sends a transaction through it — it's kept here only for building the
# app.ens.domains verification links this module's docstring/README
# point judges at, and for any future read-side convenience lookup.
ENS_UNIVERSAL_RESOLVER_ADDRESS = "0xeEeEEEeE14D718C2B47D9923Deab1335E144EeEe"

PARENT_LABEL = "agentria"  # PARENT_NAME's single label under .eth

SEPOLIA_CHAIN_ID = 11155111

# --- ENSv2 Enhanced Access Control role bitmaps -------------------------
#
# Verified against the real, currently-deployed
# contracts/src/registry/libraries/RegistryRolesLib.sol and
# contracts/src/resolver/libraries/PermissionedResolverLib.sol in
# ensdomains/contracts-v2. See ens/eac.py for the shared bitmap math
# (ROOT_RESOURCE fallback, admin-implies-grantable semantics) these
# constants plug into.

# RegistryRolesLib (PermissionedRegistry / UserRegistry roles).
ROLE_REGISTRAR = 1 << 0
ROLE_REGISTRAR_ADMIN = ROLE_REGISTRAR << 128
ROLE_UNREGISTER = 1 << 12
ROLE_UNREGISTER_ADMIN = ROLE_UNREGISTER << 128
ROLE_RENEW = 1 << 16
ROLE_RENEW_ADMIN = ROLE_RENEW << 128
ROLE_SET_SUBREGISTRY = 1 << 20
ROLE_SET_SUBREGISTRY_ADMIN = ROLE_SET_SUBREGISTRY << 128
ROLE_SET_RESOLVER = 1 << 24
ROLE_SET_RESOLVER_ADMIN = ROLE_SET_RESOLVER << 128
ROLE_CAN_TRANSFER_ADMIN = (1 << 28) << 128

# Everything a fresh subregistry's owner needs to manage it going
# forward: register/reserve children, renew, unregister, repoint their
# subregistry/resolver, and receive transfers -- granted to `admin` at
# UserRegistry.initialize() time by register.py's ensure_subregistry().
SUBREGISTRY_ADMIN_ROLE_BITMAP = (
    ROLE_REGISTRAR
    | ROLE_REGISTRAR_ADMIN
    | ROLE_UNREGISTER
    | ROLE_UNREGISTER_ADMIN
    | ROLE_RENEW
    | ROLE_RENEW_ADMIN
    | ROLE_SET_SUBREGISTRY
    | ROLE_SET_SUBREGISTRY_ADMIN
    | ROLE_SET_RESOLVER
    | ROLE_SET_RESOLVER_ADMIN
    | ROLE_CAN_TRANSFER_ADMIN
)

# PermissionedResolverLib (PermissionedResolver roles).
ROLE_SET_TEXT = 1 << 4
ROLE_SET_TEXT_ADMIN = ROLE_SET_TEXT << 128
ROLE_UPGRADE = 1 << 124
ROLE_UPGRADE_ADMIN = ROLE_UPGRADE << 128

# Granted to `admin` at PermissionedResolver.initialize() time: enough to
# call authorizeNameRoles() (grant/revoke ROLE_SET_TEXT per node) and to
# authorize future UUPS upgrades -- deliberately *not* the plain
# ROLE_SET_TEXT bit itself, so admin can delegate write access to each
# agent's own derived key without ever being able to write records
# through this resolver directly (see ens/eac.py's admin-vs-regular-bit
# note).
RESOLVER_ADMIN_ROLE_BITMAP = ROLE_SET_TEXT_ADMIN | ROLE_UPGRADE_ADMIN

# The exact function signatures RIA calls (used by ens/abi.py's Function
# helper to build calldata) are verified directly against the real,
# currently-deployed contract source —
# contracts/src/registry/PermissionedRegistry.sol,
# contracts/src/registry/UserRegistry.sol,
# contracts/src/resolver/PermissionedResolver.sol in
# ensdomains/contracts-v2, and src/VerifiableFactory.sol in
# ensdomains/verifiable-factory — and defined alongside their call sites
# in ens/registry.py, ens/resolver.py and ens/factory.py rather than
# duplicated here.
