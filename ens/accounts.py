"""Signing accounts: one funded admin wallet, four derived agent wallets.

RIA only asks the operator to fund and hold one Sepolia wallet
(`ENS_PRIVATE_KEY`) — it owns `ria.eth` and pays gas. Each of the 4 agents
still needs its *own* distinct signing key though, because the whole point
of the Permissioned Resolver check in resolver.py is that a write is
authorised by *whose key signed it*, not by an `agent_id` string the caller
could just claim. If every agent shared one key, "EXEC can't write
ORACLE's records" would be unenforceable by construction.

So each agent's key is deterministically derived from the admin key plus
its agent_id: same admin key in -> same 4 agent addresses out, every time,
with no extra secrets to fund or store. This is a plain KDF
(keccak(admin_key || agent_id)), not BIP-32 — fine for isolating demo
accounts under one testnet wallet, not a production custody pattern.
"""

from __future__ import annotations

import os

from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import keccak

ENS_PRIVATE_KEY_ENV = "ENS_PRIVATE_KEY"


class MissingCredentialError(RuntimeError):
    """Raised when ENS_PRIVATE_KEY isn't set — never mock a fake key."""


def has_admin_key() -> bool:
    """True iff ENS_PRIVATE_KEY is configured. Never reads/prints the value."""
    return bool(os.environ.get(ENS_PRIVATE_KEY_ENV))


def load_admin_account() -> LocalAccount:
    """Load the funded Sepolia wallet that owns `ria.eth` and pays gas.

    Raises MissingCredentialError rather than falling back to a mocked key
    — a live-looking registration against a fake account is worse than no
    registration at all.
    """
    private_key = os.environ.get(ENS_PRIVATE_KEY_ENV)
    if not private_key:
        raise MissingCredentialError(
            f"{ENS_PRIVATE_KEY_ENV} is not set. Fund a Sepolia wallet from a "
            "faucet, export its private key as this env var, and make sure "
            "it owns ria.eth on Sepolia before running ens/register.py live. "
            "See README.md > Environment Variables."
        )
    return Account.from_key(private_key)


def derive_agent_account(admin: LocalAccount, agent_id: str) -> LocalAccount:
    """Deterministically derive one agent's distinct Sepolia signing key.

    Same admin key + agent_id always yields the same account, so re-running
    registration doesn't orphan previously-granted on-chain approvals.
    """
    admin_key_bytes = admin.key if isinstance(admin.key, bytes) else bytes(admin.key)
    derived_key = keccak(admin_key_bytes + agent_id.encode("utf-8"))
    return Account.from_key(derived_key)
