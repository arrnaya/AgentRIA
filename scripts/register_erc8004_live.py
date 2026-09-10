"""ONE-OFF LIVE SCRIPT -- deploys RIA's ERC-8004 Identity Registry and
registers RECON/ORACLE/EXEC/AUDIT on Hedera TESTNET for real. Spends real
(free, testnet-only) HBAR on network fees (file upload, contract deploy,
4x register, plus a couple of setMetadata calls) and is not cleanly
undoable, so it's never wired into CI and should only be run deliberately.

Standalone, like `scripts/register_agents_live.py` (the Sepolia/ENS
equivalent) and `scripts/hcs_smoke_test.py`: this agent's Bash tool is
hard-denied from reading `.env*` files, so it cannot run this itself --
see `.claude/agents/hedera-payments-engineer.md` > Credentials. Run it
yourself; it never fabricates a file id, contract id, agent id, tx id, or
HashScan link -- if any step fails, it prints the real error and exits
non-zero.

What this run actually does (see hedera/erc8004.py's module docstring for
the full design rationale -- native Hedera Smart Contract Service via
hiero_sdk_python, ERC-721-lite single-file contract, data: URI agentURIs):

  1. Loads HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY (disambiguated via
     hedera/key_loader.py -- see its docstring for why not
     PrivateKey.from_string() directly).
  2. Deploys RIAIdentityRegistry (hedera/contracts/RIAIdentityRegistry.sol,
     compiled to hedera/contracts/RIAIdentityRegistry.json) via
     FileCreateTransaction/FileAppendTransaction + ContractCreateTransaction
     -- unless ERC8004_REGISTRY_CONTRACT_ID is set, in which case that
     existing contract is reused instead of deploying a second one.
  3. Registers RECON, ORACLE, EXEC, AUDIT (in that fixed order, matching
     ens/constants.py's SUBNAME_TABLE) via register(string agentURI),
     each with its own self-contained data: URI registration document
     (hedera/erc8004.py's build_agent_uri()) plus one setMetadata() call
     for "capabilities".
  4. Runs a live, read-only verify_agent() (ownerOf + tokenURI) against
     each just-registered agent id as a direct, executable confirmation
     that registration really landed on-chain -- not just that the
     transaction didn't raise.

Preconditions:
  - HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY set to a funded Hedera TESTNET
    account (free from the Hedera Testnet Portal faucet).
  - Optionally ERC8004_REGISTRY_CONTRACT_ID (e.g. "0.0.xxxxx"), to reuse a
    registry deployed by a previous run instead of deploying a new one --
    this script prints it at the end specifically so it can be fed back
    in here next time.

Usage:
    export HEDERA_ACCOUNT_ID=0.0.xxxxx
    export HEDERA_PRIVATE_KEY=...
    # export ERC8004_REGISTRY_CONTRACT_ID=0.0.xxxxx   # optional, reuse
    python -m scripts.register_erc8004_live          # interactive confirm
    python -m scripts.register_erc8004_live --yes     # skip the prompt

This script never reads or prints HEDERA_PRIVATE_KEY's value -- only
whether it's set.
"""

from __future__ import annotations

import argparse
import os
import sys

from hedera.erc8004 import (
    AGENT_TABLE,
    Erc8004ConfigError,
    Erc8004DeployError,
    Erc8004RegisterError,
    build_agent_uri,
    build_operator,
    deploy_registry,
    register_agent,
    verify_agent,
)
from hiero_sdk_python import ContractId

REGISTRY_CONTRACT_ENV = "ERC8004_REGISTRY_CONTRACT_ID"

# Fixed registration order -- matches ens/constants.py's SUBNAME_TABLE
# (RECON, ORACLE, EXEC, AUDIT; SCOUT/RISK are internal-only and never get
# an identity on either chain).
AGENT_ORDER = ["recon", "oracle", "exec", "audit"]


def _hashscan_tx_url(tx_id: str) -> str:
    # hiero_sdk_python's TransactionId prints as "0.0.X@seconds.nanos"
    # (see transaction_id.py's to_string()), but HashScan's URL scheme
    # wants "0.0.X-seconds-nanos" -- confirmed against README's own live
    # x402 settlement link, which uses that dashed form. Only the
    # "@" and the seconds/nanos "." need converting; the account id's own
    # "0.0.X" dots must stay untouched.
    account_part, _, time_part = tx_id.partition("@")
    return f"https://hashscan.io/testnet/transaction/{account_part}-{time_part.replace('.', '-')}"


def _hashscan_contract_url(contract_id: str) -> str:
    return f"https://hashscan.io/testnet/contract/{contract_id}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt.")
    args = parser.parse_args()

    print("=" * 70)
    print("LIVE Hedera TESTNET ERC-8004 registration -- spends real (testnet)")
    print("HBAR and cannot be cleanly undone (contract deployment + agent")
    print("registrations will be set on-chain).")
    print("=" * 70)

    account_id_str = os.environ.get("HEDERA_ACCOUNT_ID")
    private_key_str = os.environ.get("HEDERA_PRIVATE_KEY")
    registry_override = os.environ.get(REGISTRY_CONTRACT_ENV)

    missing = [n for n, v in (("HEDERA_ACCOUNT_ID", account_id_str), ("HEDERA_PRIVATE_KEY", private_key_str)) if not v]
    if missing:
        print(f"FAILED - missing required env var(s): {', '.join(missing)}")
        return 1

    print(f"Account:  {account_id_str}")
    if registry_override:
        print(f"Registry: {registry_override}  (reusing, from {REGISTRY_CONTRACT_ENV})")
    else:
        print(f"Registry: will deploy a fresh RIAIdentityRegistry contract (set {REGISTRY_CONTRACT_ENV} to reuse one instead)")
    print("Agents to register, in order:")
    for key in AGENT_ORDER:
        print(f"  - {AGENT_TABLE[key]['name']} ({key}) -- capabilities: {AGENT_TABLE[key]['capabilities']}")

    if not args.yes:
        confirm = input("\nType REGISTER to proceed: ")
        if confirm.strip() != "REGISTER":
            print("Aborted -- no transactions sent.")
            return 1

    try:
        account_id, private_key, client = build_operator(account_id_str, private_key_str)
    except Erc8004ConfigError as exc:
        print(f"FAILED - could not build operator: {exc}")
        return 1

    if registry_override:
        contract_id = ContractId.from_string(registry_override)
        print(f"\nReusing registry contract {contract_id}")
    else:
        print("\nDeploying RIAIdentityRegistry (uploads bytecode + creates contract)...")
        try:
            deployment = deploy_registry(client, private_key)
        except Erc8004DeployError as exc:
            print(f"FAILED - could not deploy RIAIdentityRegistry: {exc}")
            return 1
        contract_id = ContractId.from_string(deployment.contract_id)
        print(f"Deployed: contract_id={deployment.contract_id}  evm_address=0x{deployment.contract_evm_address}")
        print(f"HashScan: {_hashscan_contract_url(deployment.contract_id)}")
        print(f"Save as {REGISTRY_CONTRACT_ENV}={deployment.contract_id} to reuse this registry next run.")

    print("\nRegistering agents...\n")
    registrations = []
    for key in AGENT_ORDER:
        info = AGENT_TABLE[key]
        agent_uri = build_agent_uri(key)
        try:
            reg = register_agent(
                client,
                account_id,
                private_key,
                contract_id,
                agent_key=key,
                agent_uri=agent_uri,
                metadata={"capabilities": info["capabilities"].encode()},
            )
        except Erc8004RegisterError as exc:
            print(f"FAILED - could not register {info['name']}: {exc}")
            return 1

        print(f"{reg.name} ({key}) -> agent_id={reg.agent_id}")
        print(f"  global_agent_id: {reg.global_agent_id}")
        print(f"  register tx:     {reg.register_tx_id}  ({_hashscan_tx_url(reg.register_tx_id)})")
        for meta_key, tx_id in reg.metadata_tx_ids.items():
            print(f"  setMetadata({meta_key}) tx: {tx_id}")

        try:
            verified = verify_agent(client, contract_id, reg.agent_id)
        except Exception as exc:  # pragma: no cover - live-only, defensive
            print(f"  WARNING - could not verify on-chain read-back: {exc}")
        else:
            print(f"  verified ownerOf({reg.agent_id})  = 0x{verified['owner']}")
            print(f"  verified tokenURI({reg.agent_id}) = {verified['token_uri'][:60]}...")
        print()
        registrations.append(reg)

    print("Done. All 4 agents registered on-chain.\n")
    print(f"Registry contract ({REGISTRY_CONTRACT_ENV} for reuse): {contract_id}")
    for reg in registrations:
        print(f"  {reg.name}: agent_id={reg.agent_id}  global_agent_id={reg.global_agent_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
