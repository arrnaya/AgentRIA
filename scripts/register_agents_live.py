"""ONE-OFF LIVE SCRIPT -- registers RIA's 4 ENS subnames on Sepolia for real.

This is deliberately kept separate from ens/register.py (which is a pure,
fully-unit-tested library with no network access of its own). Running
*this* script sends real transactions on Sepolia testnet: it spends real
(test) ETH from ENS_PRIVATE_KEY's wallet and is hard to cleanly undo, so it
is never wired into CI and should only be run deliberately, once you're
confident in the resolver logic.

What this run actually does (ENSv2, not ENSv1 -- see ens/registry.py and
ens/resolver.py's module docstrings for the full verification):

  1. Looks up agentria.eth's subregistry (getSubregistry("agentria") on
     ENS_ETH_REGISTRY_ADDRESS). If none exists yet -- confirmed true as of
     writing via a live read-only call -- deploys one (a UserRegistry
     proxy, via ENSv2's VerifiableFactory) and attaches it.
  2. Deploys one shared PermissionedResolver proxy for all four subnames
     (unless RIA_RESOLVER_ADDRESS points at one from a previous run).
     ENSv2's Enhanced Access Control roles are scoped per node internally,
     so one shared instance still gives each agent an isolated grant --
     see ens/resolver.py's module docstring for why four separate
     instances aren't needed.
  3. Registers recon/oracle/exec/audit.agentria.eth inside that
     subregistry, each owned by the admin wallet, resolved through that
     shared resolver.
  4. Grants each agent's own derived key (ens/accounts.py) ROLE_SET_TEXT
     on *its own* node only, funds it, and has it sign its own set_text
     calls for its ENSIP-26 records.
  5. Runs verify_isolation() as a direct, executable check that no
     agent's key can write another agent's records.

Preconditions:
  - ENS_PRIVATE_KEY set to a Sepolia wallet's private key, funded from a
    faucet (e.g. https://sepoliafaucet.com), that already owns `agentria.eth`
    on Sepolia (register the parent name yourself first at
    https://sepolia.app.ens.domains if you haven't -- confirmed already
    done for agentria.eth as of writing this script).
  - SEPOLIA_RPC_URL set to an RPC endpoint (Infura/Alchemy/public gateway).
  - Optionally RIA_SUBREGISTRY_ADDRESS / RIA_RESOLVER_ADDRESS, to reuse
    proxies deployed by a previous run instead of deploying new ones (see
    ens/register.py's ensure_subregistry()/ensure_resolver()) -- this
    script prints both addresses at the end specifically so they can be
    fed back in here next time.

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

from ens.accounts import ENS_PRIVATE_KEY_ENV, has_admin_key, load_admin_account
from ens.constants import ENS_ETH_REGISTRY_ADDRESS, PARENT_NAME, SUBNAME_TABLE
from ens.register import ensure_resolver, ensure_subregistry, register_all, verify_isolation
from ens.registry import PermissionedRegistryClient
from ens.rpc import SepoliaRpcClient

SEPOLIA_RPC_ENV = "SEPOLIA_RPC_URL"
SUBREGISTRY_ENV = "RIA_SUBREGISTRY_ADDRESS"
RESOLVER_ENV = "RIA_RESOLVER_ADDRESS"


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

    subregistry_override = os.environ.get(SUBREGISTRY_ENV)
    resolver_override = os.environ.get(RESOLVER_ENV)

    print("=" * 70)
    print("LIVE Sepolia ENS registration -- this spends real testnet ETH")
    print("and cannot be cleanly undone (subname ownership + resolver")
    print("records will be set on-chain).")
    print("=" * 70)
    print(f"Parent name:          {PARENT_NAME}")
    print(f"Root .eth registry:   {ENS_ETH_REGISTRY_ADDRESS}")
    print(f"RPC:                  {rpc_url}")
    if subregistry_override:
        print(f"Subregistry:          {subregistry_override}  (reusing, from {SUBREGISTRY_ENV})")
    else:
        print("Subregistry:          looked up live; deployed fresh if none exists yet")
    if resolver_override:
        print(f"Resolver:             {resolver_override}  (reusing, from {RESOLVER_ENV})")
    else:
        print(f"Resolver:             deployed fresh (set {RESOLVER_ENV} to reuse one instead)")
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
    root_registry = PermissionedRegistryClient(rpc=rpc, address=ENS_ETH_REGISTRY_ADDRESS)

    subregistry = ensure_subregistry(rpc, root_registry, admin, override_address=subregistry_override)
    print(f"\nSubregistry ready: {subregistry.address}")

    resolver = ensure_resolver(rpc, admin, override_address=resolver_override)
    print(f"Resolver ready:    {resolver.address}")

    registrations = register_all(
        rpc=rpc, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )
    verify_isolation(resolver, registrations)

    print("\nDone. Isolation verified on-chain: no agent's key can write ")
    print("another agent's records.\n")
    print(f"Subregistry (save as {SUBREGISTRY_ENV} to reuse next run): {subregistry.address}")
    print(f"Resolver    (save as {RESOLVER_ENV} to reuse next run):    {resolver.address}\n")
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
