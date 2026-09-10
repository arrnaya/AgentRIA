"""Registers RIA's 4 agent subnames under ria.eth with isolated write access.

Pure orchestration over ens/accounts.py, ens/namehash.py, ens/abi.py and
ens/resolver.py -- every network call here goes through an injected `rpc`
and `resolver`, so this module is fully unit-testable against a
hand-written fake EthRpc (see tests/test_ens_register.py) with no live
Sepolia dependency.

This file is NOT the live entrypoint. Running it directly does nothing --
the one-off script that actually spends real testnet ETH is
scripts/register_agents_live.py, which builds a real SepoliaRpcClient,
loads ENS_PRIVATE_KEY, and calls register_all() below. Keeping that wiring
out of this file is deliberate: it's expensive, hard to undo, and should
never run by accident (in CI or otherwise).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from eth_account.signers.local import LocalAccount

from ens.abi import Function
from ens.accounts import derive_agent_account
from ens.constants import PARENT_NAME, SUBNAME_TABLE, AgentIdentity
from ens.namehash import labelhash, namehash
from ens.resolver import PermissionedResolver
from ens.rpc import EthRpc, build_and_send

logger = logging.getLogger("ria.ens.register")

# Verified against the real, currently-deployed
# contracts/registry/ENSRegistry.sol in ensdomains/ens-contracts.
SET_SUBNODE_RECORD_FN = Function(
    "setSubnodeRecord", ("bytes32", "bytes32", "address", "address", "uint64")
)

# register_subname() has each agent sign its OWN set_text transactions
# (see that function's docstring, step 3) -- and on Sepolia, like any EVM
# chain, whoever signs a transaction pays its gas from their own balance.
# A freshly-derived agent account (ens/accounts.py) starts at zero ETH, so
# without funding it first, its first set_text would revert with
# "insufficient funds" before ever reaching the resolver's authorised()
# check. 0.005 ETH covers this table's handful of records per agent many
# times over at Sepolia's typical gas price, funded from the one admin
# wallet the operator already provides -- no extra faucet trip per agent.
FUNDING_WEI = 5_000_000_000_000_000  # 0.005 ETH


@dataclass
class SubnameRegistration:
    """Result of registering, isolating, and populating one agent's subname."""

    agent_id: str
    name: str
    node: bytes
    operator_address: str
    records: dict[str, str]


def register_subname(
    identity: AgentIdentity,
    *,
    rpc: EthRpc,
    resolver: PermissionedResolver,
    admin: LocalAccount,
) -> SubnameRegistration:
    """Register one `ria-<agent>.ria.eth` subname and isolate its writes.

    1. ENSRegistry.setSubnodeRecord(parent, label, owner=admin, resolver)
       -- creates the subnode, owned by admin, resolved through our
       Permissioned Resolver.
    2. resolver.grant_operator(node, agent_address, signer=admin) -- admin,
       as this node's registry owner, approves *exactly* this agent's own
       derived address to write this node's records. No other node is
       touched, so no other agent's address is ever approved here.
    3. A plain ETH transfer, admin -> agent_account, funding the gas this
       agent needs to sign its own transactions next (see FUNDING_WEI).
    4. resolver.set_text(node, key, value, signer=agent_account) for each
       ENSIP-26 record -- signed by the agent's *own* derived key, not
       admin's, so a live run exercises the real write path an agent would
       use, not a shortcut through the owner account.
    """
    parent_node = namehash(PARENT_NAME)
    label = labelhash(identity.label)
    node = namehash(identity.name)

    data = SET_SUBNODE_RECORD_FN.encode_call(parent_node, label, admin.address, resolver.address, 0)
    build_and_send(rpc, resolver.registry_address, data, admin)
    logger.info("register: %s created, owner=admin, resolver=%s", identity.name, resolver.address)

    agent_account = derive_agent_account(admin, identity.agent_id)
    resolver.grant_operator(node, agent_account.address, signer=admin)
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
    *, rpc: EthRpc, resolver: PermissionedResolver, admin: LocalAccount
) -> list[SubnameRegistration]:
    """Register every subname in the fixed table (see ens/constants.py)."""
    return [
        register_subname(identity, rpc=rpc, resolver=resolver, admin=admin)
        for identity in SUBNAME_TABLE.values()
    ]


def verify_isolation(
    resolver: PermissionedResolver, registrations: list[SubnameRegistration]
) -> None:
    """Assert no agent's operator key is approved for any *other* agent's
    node. This is the judging bar from README's Hackathon Qualification
    Mapping made executable: run it right after register_all() (live or
    against a mock in a test) as a direct check that write isolation
    holds, not just that registration didn't error.
    """
    for reg in registrations:
        for other in registrations:
            if other.agent_id == reg.agent_id:
                continue
            if resolver.is_approved(other.node, reg.operator_address):
                raise AssertionError(
                    f"{reg.agent_id}'s operator ({reg.operator_address}) is "
                    f"unexpectedly approved to write {other.agent_id}'s node "
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
