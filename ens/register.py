"""Registers RIA's 4 agent subnames under agentria.eth with isolated write access.

Pure orchestration over ens/accounts.py, ens/namehash.py, ens/registry.py,
ens/resolver.py and ens/factory.py -- every network call here goes through
an injected `rpc`, so this module is fully unit-testable against a
hand-written fake EthRpc (see tests/fake_chain.py) with no live Sepolia
dependency.

This file is NOT the live entrypoint. Running it directly does nothing --
the one-off script that actually spends real testnet ETH is
scripts/register_agents_live.py, which builds a real SepoliaRpcClient,
loads ENS_PRIVATE_KEY, and calls register_all() below. Keeping that wiring
out of this file is deliberate: it's expensive, hard to undo, and should
never run by accident (in CI or otherwise).

ENSv2's hierarchical registry model (see ens/registry.py's module
docstring for the on-chain verification) means "register a subname" is
not the single ENSv1-shaped setSubnodeRecord() call an earlier version of
this file made. Getting recon/oracle/exec/audit.agentria.eth live takes
three separate on-chain pieces, each resolved dynamically rather than
hardcoded:

 1. agentria.eth's own *subregistry* -- a separate PermissionedRegistry
    instance that holds recon/oracle/exec/audit as its own child labels.
    A live getSubregistry("agentria") call against ENS_ETH_REGISTRY_ADDRESS
    returned the zero address, i.e. agentria.eth doesn't have one yet --
    ensure_subregistry() deploys one (via ENSv2's VerifiableFactory) the
    first time this runs, and set_subregistry()s it onto agentria.eth's
    entry in the root .eth registry.
 2. A resolver that actually understands ENSv2's Enhanced Access Control
    roles (ens/resolver.py's PermissionedResolver) -- deployed once the
    same way, and shared by all four subnames (EAC scopes every grant by
    node internally, see resolver.py's module docstring, so one shared
    resolver instance still gives each agent an isolated grant). This is
    *not* the resolver agentria.eth's own top-level name currently
    resolves through -- that's a separate, unrelated contract instance
    (confirmed on-chain; see ens/registry.py's citation).
 3. Each subname itself, registered as a label inside that subregistry,
    owned by `admin` (never by the agent -- see register_subname()'s
    docstring for why), then given exactly one authorised writer: that
    agent's own derived key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from eth_account.signers.local import LocalAccount

from ens.accounts import derive_agent_account
from ens.constants import (
    ENS_ETH_REGISTRY_ADDRESS,
    ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS,
    ENS_USER_REGISTRY_IMPL_ADDRESS,
    ENS_VERIFIABLE_FACTORY_ADDRESS,
    PARENT_LABEL,
    PARENT_NAME,
    SUBNAME_TABLE,
    SUBREGISTRY_ADMIN_ROLE_BITMAP,
    AgentIdentity,
)
from ens.factory import deploy_proxy
from ens.namehash import label_id, namehash
from ens.registry import ZERO_ADDRESS, USER_REGISTRY_INITIALIZE_FN, PermissionedRegistryClient
from ens.resolver import PermissionedResolver, deploy_resolver_proxy
from ens.rpc import EthRpc, build_and_send
from eth_utils import keccak

logger = logging.getLogger("ria.ens.register")

# register_subname() has each agent sign its OWN set_text transactions
# (see that function's docstring) -- and on Sepolia, like any EVM chain,
# whoever signs a transaction pays its gas from their own balance. A
# freshly-derived agent account (ens/accounts.py) starts at zero ETH, so
# without funding it first, its first set_text would revert with
# "insufficient funds" before ever reaching the resolver's onlyPartRoles
# check. 0.005 ETH covers this table's handful of records per agent many
# times over at Sepolia's typical gas price, funded from the one admin
# wallet the operator already provides -- no extra faucet trip per agent.
FUNDING_WEI = 5_000_000_000_000_000  # 0.005 ETH

# Deterministic salts for the two proxies this module deploys, so
# re-running register_all() with the *same* admin key always targets the
# same (sender, salt) pair -- see ens/factory.py's module docstring for
# why a second deployment attempt then fails loudly instead of silently
# drifting to a different address.
_SUBREGISTRY_SALT = int.from_bytes(keccak(text="ria-agentria-subregistry-v1"), "big")
_RESOLVER_SALT = int.from_bytes(keccak(text="ria-agentria-resolver-v1"), "big")


@dataclass
class SubnameRegistration:
    """Result of registering, isolating, and populating one agent's subname."""

    agent_id: str
    name: str
    node: bytes
    operator_address: str
    records: dict[str, str]


def ensure_subregistry(
    rpc: EthRpc,
    root_registry: PermissionedRegistryClient,
    admin: LocalAccount,
    *,
    override_address: str | None = None,
) -> PermissionedRegistryClient:
    """Return agentria.eth's subregistry, attached to its root-registry
    entry -- deploying and/or attaching one as needed.

    Always checks live attachment first (getSubregistry("agentria")),
    regardless of `override_address` -- deploying a proxy and attaching it
    are two separate transactions, and if a previous run's process died,
    crashed, or hit a transient RPC error between them (this has happened
    in practice: an in-flight-transaction-limit rejection from a provider
    on the *second* call), the proxy exists on-chain but agentria.eth
    still doesn't point at it. An earlier version of this function
    trusted `override_address` to mean "already fully done" and returned
    immediately without checking -- which would have silently left the
    subregistry unattached and every subname registered into it
    unresolvable via standard ENS resolution. Re-running this function is
    always safe: it never re-deploys (or re-attaches) something that's
    already live.

    `override_address` only controls whether a *new* proxy gets deployed
    if none is attached yet: pass the address from a previous run's
    (possibly interrupted) deployment (e.g. RIA_SUBREGISTRY_ADDRESS) to
    reuse it -- required if that deployment already happened, since
    VerifiableFactory's CREATE2 deployment reverts the second time for the
    same (signer, salt) pair. Omit it to deploy fresh.
    """
    existing = root_registry.get_subregistry(PARENT_LABEL)
    if existing.lower() != ZERO_ADDRESS.lower():
        logger.info("subregistry: already attached for %s: %s", PARENT_NAME, existing)
        return PermissionedRegistryClient(rpc=rpc, address=existing)

    if override_address:
        address = override_address
        logger.info(
            "subregistry: using override %s for %s (not yet attached on-chain -- attaching now)",
            address, PARENT_NAME,
        )
    else:
        init_data = USER_REGISTRY_INITIALIZE_FN.encode_call(admin.address, SUBREGISTRY_ADMIN_ROLE_BITMAP)
        address = deploy_proxy(
            rpc,
            ENS_VERIFIABLE_FACTORY_ADDRESS,
            ENS_USER_REGISTRY_IMPL_ADDRESS,
            _SUBREGISTRY_SALT,
            init_data,
            signer=admin,
        )
        logger.info("subregistry: deployed a new one for %s at %s", PARENT_NAME, address)

    root_registry.set_subregistry(label_id(PARENT_LABEL), address, signer=admin)
    logger.info("subregistry: attached to %s's root-registry entry", PARENT_NAME)

    return PermissionedRegistryClient(rpc=rpc, address=address)


def ensure_resolver(
    rpc: EthRpc,
    admin: LocalAccount,
    *,
    override_address: str | None = None,
) -> PermissionedResolver:
    """Return the shared PermissionedResolver proxy RIA's four subnames
    use, deploying one if `override_address` isn't given. Unlike the
    subregistry, there's no "does this already exist" on-chain lookup for
    a resolver that isn't yet attached to any name -- if this has already
    been run once, pass its address back in (e.g. RIA_RESOLVER_ADDRESS)
    rather than deploying a second one."""
    if override_address:
        return PermissionedResolver(rpc=rpc, address=override_address)

    resolver = deploy_resolver_proxy(
        rpc,
        factory_address=ENS_VERIFIABLE_FACTORY_ADDRESS,
        implementation_address=ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS,
        admin=admin,
        salt=_RESOLVER_SALT,
    )
    logger.info("resolver: deployed a new shared PermissionedResolver proxy at %s", resolver.address)
    return resolver


def register_subname(
    identity: AgentIdentity,
    *,
    rpc: EthRpc,
    subregistry: PermissionedRegistryClient,
    resolver: PermissionedResolver,
    admin: LocalAccount,
    expiry: int,
) -> SubnameRegistration:
    """Register one `<agent>.agentria.eth` subname and isolate its writes.

    1. subregistry.register(label, owner=admin, subregistry=0x0,
       resolver=resolver.address, roleBitmap=0, expiry) -- creates the
       label inside agentria.eth's subregistry, owned by admin (not the
       agent: registry-level roles like ROLE_SET_RESOLVER/ROLE_UNREGISTER
       control whether the *name itself* can be deleted, transferred, or
       repointed, and only admin should ever hold those -- an agent's
       compromised key should at most be able to rewrite its own text
       records, never delete or hijack the name). roleBitmap=0 means the
       agent gets zero registry-level roles.
    2. resolver.authorize_agent(name, agent_address, signer=admin) --
       admin, as this resolver proxy's ROOT_RESOURCE admin, grants
       *exactly* this agent's own derived address ROLE_SET_TEXT scoped to
       this one node. No other node is touched, so no other agent's
       address is ever authorised here (see resolver.py's module
       docstring for the on-chain isolation guarantee this rests on).
    3. A plain ETH transfer, admin -> agent_account, funding the gas this
       agent needs to sign its own transactions next (see FUNDING_WEI).
    4. resolver.set_text(node, key, value, signer=agent_account) for each
       ENSIP-26 record -- signed by the agent's *own* derived key, not
       admin's, so a live run exercises the real write path an agent
       would use, not a shortcut through the admin account.
    """
    node = namehash(identity.name)

    subregistry.register(
        identity.label, admin.address, ZERO_ADDRESS, resolver.address, 0, expiry, signer=admin
    )
    logger.info(
        "register: %s created in subregistry, owner=admin, resolver=%s",
        identity.name, resolver.address,
    )

    agent_account = derive_agent_account(admin, identity.agent_id)
    resolver.authorize_agent(identity.name, agent_account.address, signer=admin)
    logger.info("register: %s write access granted to %s only", identity.name, agent_account.address)

    build_and_send(rpc, agent_account.address, b"", admin, value=FUNDING_WEI)
    logger.info(
        "register: funded %s with %.4f ETH for its own set_text gas",
        agent_account.address, FUNDING_WEI / 1e18,
    )

    records = identity.text_records()
    for key, value in records.items():
        resolver.set_text(node, key, value, signer=agent_account)
        logger.info("register: %s %s=%r (signed by agent's own key)", identity.name, key, value)

    return SubnameRegistration(
        agent_id=identity.agent_id,
        name=identity.name,
        node=node,
        operator_address=agent_account.address,
        records=records,
    )


def register_all(
    *,
    rpc: EthRpc,
    subregistry: PermissionedRegistryClient,
    resolver: PermissionedResolver,
    admin: LocalAccount,
    root_registry: PermissionedRegistryClient | None = None,
    expiry: int | None = None,
) -> list[SubnameRegistration]:
    """Register every subname in the fixed table (see ens/constants.py).

    `expiry` defaults to agentria.eth's own current expiry (read live from
    `root_registry`, or ENS_ETH_REGISTRY_ADDRESS if `root_registry` isn't
    given) so RIA's subnames never silently outlive the parent name --
    pass it explicitly (e.g. in tests) to skip that lookup.
    """
    if expiry is None:
        registry_for_expiry = root_registry or PermissionedRegistryClient(
            rpc=rpc, address=ENS_ETH_REGISTRY_ADDRESS
        )
        expiry = registry_for_expiry.get_expiry(label_id(PARENT_LABEL))

    return [
        register_subname(
            identity, rpc=rpc, subregistry=subregistry, resolver=resolver, admin=admin, expiry=expiry
        )
        for identity in SUBNAME_TABLE.values()
    ]


def verify_isolation(
    resolver: PermissionedResolver, registrations: list[SubnameRegistration]
) -> None:
    """Assert no agent's operator key holds ROLE_SET_TEXT on any *other*
    agent's node. This is the judging bar from README's Hackathon
    Qualification Mapping made executable: run it right after
    register_all() (live or against a mock in a test) as a direct check
    that write isolation holds, not just that registration didn't error.
    """
    for reg in registrations:
        for other in registrations:
            if other.agent_id == reg.agent_id:
                continue
            if resolver.is_authorized_for_node(other.node, reg.operator_address):
                raise AssertionError(
                    f"{reg.agent_id}'s operator ({reg.operator_address}) is "
                    f"unexpectedly authorised to write {other.agent_id}'s node "
                    f"({other.name}) -- write isolation is broken."
                )


if __name__ == "__main__":
    print(
        "ens/register.py is a library of testable functions, not the live "
        "entrypoint -- running it directly does nothing.\n"
        "To actually register subnames on Sepolia (spends real testnet "
        "ETH, hard to undo), run:\n\n"
        "    python -m scripts.register_agents_live\n"
    )
