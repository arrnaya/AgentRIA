"""ONE-OFF LIVE SCRIPT -- registers RIA's 4 ENS subnames on Sepolia for real.

This is deliberately kept separate from ens/register.py (which is a pure,
fully-unit-tested library with no network access of its own). Running
*this* script sends real transactions on Sepolia testnet: it spends real
(test) ETH from ENS_PRIVATE_KEY's wallet and is hard to cleanly undo, so it
is never wired into CI and should only be run deliberately, once you're
confident in the resolver logic.

Preconditions:
  - ENS_PRIVATE_KEY set to a Sepolia wallet's private key, funded from a
    faucet (e.g. https://sepoliafaucet.com), that already owns `agentria.eth`
    on Sepolia (register the parent name yourself first at
    https://sepolia.app.ens.domains if you haven't).
  - SEPOLIA_RPC_URL set to an RPC endpoint (Infura/Alchemy/public gateway).
  - Optionally ENS_RESOLVER_ADDRESS set to the Permissioned Resolver proxy
    ENSv2 deployed for agentria.eth's owner (check
    https://sepolia.app.ens.domains/agentria.eth or
    https://docs.ens.domains/learn/deployments for the current address --
    ENSv2 deploys these per name-owner via its Verifiable Factory, so
    there's no single fixed constant to hardcode here). If unset, this
    falls back to Sepolia's standard PublicResolver, which exposes the
    identical node-scoped approve()/isApprovedFor() access-control profile
    this script relies on -- see ens/constants.py's ABI comment.

Usage:
    python -m scripts.register_agents_live          # interactive confirm
    python -m scripts.register_agents_live --yes     # skip the prompt

This script never reads or prints ENS_PRIVATE_KEY's value -- only whether
it's set (see ens/accounts.py).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from eth_utils import to_checksum_address

from ens.accounts import ENS_PRIVATE_KEY_ENV, has_admin_key, load_admin_account
from ens.constants import DEFAULT_PUBLIC_RESOLVER_ADDRESS, PARENT_NAME, SUBNAME_TABLE
from ens.register import register_all, verify_isolation
from ens.resolver import PermissionedResolver
from ens.rpc import SepoliaRpcClient

SEPOLIA_RPC_ENV = "SEPOLIA_RPC_URL"
RESOLVER_ENV = "ENS_RESOLVER_ADDRESS"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation prompt."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not has_admin_key():
        print(
            f"{ENS_PRIVATE_KEY_ENV} is not set. Fund a Sepolia wallet from a "
            "faucet, export its private key as this env var, and make sure "
            "it owns agentria.eth on Sepolia. Stopping -- not registering with a "
            "mocked/fake key."
        )
        return 1

    rpc_url = os.environ.get(SEPOLIA_RPC_ENV)
    if not rpc_url:
        print(f"{SEPOLIA_RPC_ENV} is not set. Set it to a Sepolia RPC endpoint.")
        return 1

    resolver_address = os.environ.get(RESOLVER_ENV, DEFAULT_PUBLIC_RESOLVER_ADDRESS)
    if not os.environ.get(RESOLVER_ENV):
        print(
            "WARNING: ENS_RESOLVER_ADDRESS is not set -- falling back to the "
            f"Sepolia PublicResolver default ({DEFAULT_PUBLIC_RESOLVER_ADDRESS}). "
            "ENSv2 deploys a fresh Permissioned Resolver proxy per name owner, "
            "so agentria.eth's real one may differ -- confirm at "
            "https://sepolia.app.ens.domains/agentria.eth before proceeding, or set "
            "ENS_RESOLVER_ADDRESS explicitly.\n"
        )

    print("=" * 70)
    print("LIVE Sepolia ENS registration -- this spends real testnet ETH")
    print("and cannot be cleanly undone (subname ownership + resolver")
    print("records will be set on-chain).")
    print("=" * 70)
    print(f"Parent name:      {PARENT_NAME}")
    print(f"Resolver address: {resolver_address}")
    print(f"RPC:              {rpc_url}")
    print("Subnames to register:")
    for identity in SUBNAME_TABLE.values():
        print(f"  - {identity.name}  (capabilities: {identity.capabilities})")

    if not args.yes:
        confirm = input("\nType REGISTER to proceed: ")
        if confirm.strip() != "REGISTER":
            print("Aborted -- no transactions sent.")
            return 1

    rpc = SepoliaRpcClient(rpc_url)
    if not rpc.is_connected():
        print(f"Could not connect to {rpc_url} -- check SEPOLIA_RPC_URL.")
        return 1

    admin = load_admin_account()
    resolver = PermissionedResolver(rpc=rpc, address=to_checksum_address(resolver_address))

    registrations = register_all(rpc=rpc, resolver=resolver, admin=admin)
    verify_isolation(resolver, registrations)

    print("\nDone. Isolation verified on-chain: no agent's key can write ")
    print("another agent's records.\n")
    for reg in registrations:
        print(reg.name)
        print(f"  operator address: {reg.operator_address}")
        print(f"  ENS app:          https://sepolia.app.ens.domains/{reg.name}")
        for key, value in reg.records.items():
            print(f"  {key} = {value}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
