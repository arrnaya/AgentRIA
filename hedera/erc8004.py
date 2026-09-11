"""ERC-8004 (draft) Identity Registry deployment + agent registration on
Hedera testnet.

Scope, per README.md > "Layer 3 -- Identity & Visibility": each RIA agent
(RECON, ORACLE, EXEC, AUDIT -- the same four ens/constants.py registers on
Sepolia) gets an on-chain ERC-8004 identity. ERC-8004 (still Draft as of
2026-09-10, re-verified directly against
https://eips.ethereum.org/EIPS/eip-8004 before writing this module --
there is no deployed reference implementation or canonical address to call
into) defines three registries: Identity, Reputation, Validation. This
module implements the Identity Registry ONLY -- Reputation and Validation
are out of scope for this repo (README only claims agent *identity*
registration, not reputation/validation).

Containment: this is a one-time identity-provisioning concern, not a
payment. It reuses `HEDERA_ACCOUNT_ID`/`HEDERA_PRIVATE_KEY` (the same
funded testnet account everything else in this repo uses, per README's
Environment Variables table) purely to pay the small Hedera network fees
for deploying a contract and calling `register`/`setMetadata` -- this is
NOT the x402 commercial payment path. Like `hedera/hcs_logger.py`, this
module deliberately does NOT import `hedera.wallet.HederaWallet` (whose
docstring reserves it for ORACLE alone) and instead builds its own
minimal operator/Client pair via `hedera.key_loader.load_private_key`, so
the containment boundary between "ORACLE's x402 payment authority" and
"everything else that happens to share a testnet operator key today"
stays visible in the code, not just in prose. Nothing here is imported by
`agents/*.py`, and this module never touches `hedera/x402_client.py`.

Deployment mechanism -- native Hedera Smart Contract Service via
`hiero_sdk_python`, NOT a separate EVM JSON-RPC relay (contrast with
`ens/rpc.py`'s Sepolia JSON-RPC path, which is a genuinely different
chain/toolchain choice for a genuinely different reason: Sepolia is
plain Ethereum, so raw JSON-RPC + eth_account was the natural fit there).
On Hedera testnet, the native Smart Contract Service reuses the exact
same `HEDERA_ACCOUNT_ID`/`HEDERA_PRIVATE_KEY` credential model as
`hedera/wallet.py` and `hedera/hcs_logger.py` -- no second RPC endpoint,
no second key format. Confirmed available on the installed
`hiero_sdk_python==0.2.10`: `FileCreateTransaction`,
`FileAppendTransaction`, `ContractCreateTransaction`,
`ContractExecuteTransaction`, `ContractCallQuery`,
`ContractFunctionParameters`. There is NO `ContractCreateFlow` (or
equivalent) in this version -- confirmed by introspecting `dir()` for
anything containing "Contract" -- so contract bytecode has to be
uploaded to the Hedera File Service first (`FileCreateTransaction` +
`FileAppendTransaction` for anything over one chunk) and then referenced
by `ContractCreateTransaction.set_bytecode_file_id()`, rather than a
single one-call deploy helper.

Gas: unused gas on a Hedera contract call/create is refunded (confirmed
via Hedera's own gas-and-fees docs, https://docs.hedera.com/hedera/core-concepts/smart-contracts/gas-and-fees
-- "users are charged only for the actual gas used ... with unused gas
being fully refunded", per EIP-3529), so the generous gas limits below
cost nothing extra on a first, possibly-imprecise deploy -- the same
"overshoot costs nothing on a cheap testnet call" logic as the Sepolia
gas-limit lesson from the ENS work, though the underlying mechanism here
(Hedera's own refund policy, not an EVM legacy-tx refund) is different --
confirmed, not assumed, per that lesson's own instruction to re-verify.

Contract source: `hedera/contracts/RIAIdentityRegistry.sol` (see its own
docstring for the ERC-721-lite design decision and why the agentURI-only
`register(string)` overload is what this module actually calls instead of
the metadata-carrying `register(string, MetadataEntry[])` one).
`hedera/contracts/RIAIdentityRegistry.json` is the compiled artifact
(abi + bytecode), generated once with `hedera/contracts/compile.py`
(solc 0.8.24 via py-solc-x) and checked into git -- so deploying/testing
this module never needs `solc` installed at runtime, only at the one time
someone edits the .sol source and regenerates the artifact.

agentURI: there is no hosted HTTP endpoint anywhere in this repo yet to
serve a registration JSON document from (the dashboard is a static
preview per README's "What's Live" table). Rather than invent a fake URL
that 404s, `build_agent_uri()` embeds the registration document directly
as a `data:application/json;base64,...` URI (RFC 2397) -- so
`tokenURI(agentId)` is *itself* the resolvable, self-contained
registration document; anyone can read it back with nothing more than an
RPC/mirror-node call and a base64 decode, no external hosting dependency
or trust required. This is a deliberate scope choice for this hackathon
build, called out explicitly rather than silently -- a production
deployment would likely serve this from `mcp_server/`'s HTTP endpoint
once one is addressable publicly.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hiero_sdk_python import (
    AccountId,
    Client,
    ContractCallQuery,
    ContractCreateTransaction,
    ContractExecuteTransaction,
    ContractFunctionParameters,
    ContractId,
    FileAppendTransaction,
    FileCreateTransaction,
    FileId,
    Hbar,
    PrivateKey,
)

from hedera.key_loader import KeyLoadError, load_private_key

logger = logging.getLogger("ria.erc8004")

# Hedera's File Service enforces roughly a 6 KiB signed-transaction size
# limit (docs.hedera.com/hedera/sdks-and-apis/sdks/file-service/create-a-file);
# 4000 bytes of the file's actual contents -- the hex-encoded bytecode
# TEXT uploaded (see deploy_registry()'s docstring for why it's the hex
# string, not decoded binary; this doubles the byte count vs. the raw
# ~3.5 KB compiled contract, to ~7 KB of hex characters, which is why the
# FileAppendTransaction path below is load-bearing for this contract, not
# just a hypothetical for a bigger one) -- leaves comfortable headroom for
# the rest of the transaction (body, signatures, node/tx ids) within that
# cap for the first FileCreateTransaction chunk. Anything beyond that goes
# through FileAppendTransaction, which chunks automatically (default
# chunk_size=4096, see hiero_sdk_python's ChunkedTransaction).
FIRST_FILE_CHUNK_BYTES = 4000

DEFAULT_CREATE_GAS = 2_000_000
# register()'s agentURI is a self-contained `data:` URI carrying the whole
# registration document (build_agent_uri()'s output is ~450-500 bytes for
# RIA's four agents) -- storing a Solidity string that size means ~15
# SSTORE operations for _agentURIs[agentId] alone (each up to ~20-22k gas
# for a first/cold write), which a real live run proved 300_000 gas
# doesn't cover (INSUFFICIENT_GAS). Bumped with real headroom -- unused
# gas is refunded on Hedera (confirmed earlier against
# docs.hedera.com/evm/development/gas-fees), so overshooting costs
# nothing on a call this cheap.
DEFAULT_EXECUTE_GAS = 1_000_000

# `transaction_fee` (the max-fee cap the payer is willing to pay -- the
# actual charged fee, reported separately in the receipt/record, is
# whatever the network's fee schedule computes, refunding the unused
# portion of the cap; confirmed via docs.hedera.com/learn/core-concepts/
# fee-model) needs explicit headroom here: hiero_sdk_python's own
# FileCreateTransaction/FileAppendTransaction default to Hbar(5), which a
# real live run proved insufficient for a ~4-7 KB file's storage-rent
# component (INSUFFICIENT_TX_FEE on FileCreate, confirmed via the
# transaction's own mirror-node record -- not a balance problem, the
# operator had ~980 HBAR). ContractExecuteTransaction has no override at
# all (falls back to the base Transaction default of Hbar(2)) -- bumped
# preemptively here rather than waiting for the same failure mode on
# register()/setMetadata() calls.
FILE_TRANSACTION_FEE = Hbar(20)
EXECUTE_TRANSACTION_FEE = Hbar(5)

# CAIP-2 for Hedera testnet's EVM-compatible chain id, per HIP-30 and
# confirmed live via web search against chainlist.org/chain/296 and
# hips.hedera.com/hip/hip-30 (mainnet=295, testnet=296, previewnet=297).
# ERC-8004's own global-id example ("eip155:1:0x742...") uses the eip155
# CAIP-2 namespace, so this module follows the same convention for
# interop with any ERC-8004-aware EVM tooling that resolves global agent
# ids, rather than Hedera's native "hedera:testnet" CAIP namespace.
HEDERA_TESTNET_CAIP2 = "eip155:296"

CONTRACT_ARTIFACT_PATH = Path(__file__).parent / "contracts" / "RIAIdentityRegistry.json"

# The fixed 4-agent table -- deliberately mirrors ens/constants.py's
# SUBNAME_TABLE (same agent_id keys, same capabilities strings) so RIA's
# Sepolia (ENSv2) and Hedera (ERC-8004) identities describe the same four
# agents the same way. Not imported from ens/constants.py directly to
# avoid a cross-layer import between two otherwise-independent identity
# systems (ENS's own module docstring notes SCOUT/RISK are internal-only
# and never get identities on either chain).
AGENT_TABLE: dict[str, dict[str, str]] = {
    "recon": {
        "name": "RECON",
        "capabilities": "data-ingestion",
        "description": "Ingests DeFi liquidation/market signals from The Graph via Subgraph Studio.",
    },
    "oracle": {
        "name": "ORACLE",
        "capabilities": "enrichment+payment",
        "description": "RIA's sole payment-authority agent -- pays for x402-gated MCP tool calls "
        "via Blocky402 on Hedera and enriches SCOUT's signals with paid data.",
    },
    "exec": {
        "name": "EXEC",
        "capabilities": "execution-gating",
        "description": "Gates and (in dry-run) simulates execution of RISK-approved actions.",
    },
    "audit": {
        "name": "AUDIT",
        "capabilities": "audit-logging",
        "description": "Writes a tamper-proof JSON audit trail of every payment and EXEC cycle to HCS.",
    },
}


class Erc8004ConfigError(RuntimeError):
    """Raised when required Hedera credentials or the artifact are missing/invalid."""


class Erc8004DeployError(RuntimeError):
    """Raised when deploying the Identity Registry contract fails."""


class Erc8004RegisterError(RuntimeError):
    """Raised when registering (or looking up) an agent fails."""


@dataclass
class RegistryDeployment:
    """Result of deploying the Identity Registry contract."""

    file_id: str
    contract_id: str
    contract_evm_address: str


@dataclass
class AgentRegistration:
    """Result of registering one agent in the Identity Registry."""

    agent_key: str
    name: str
    agent_id: int
    owner_account_id: str
    contract_id: str
    agent_uri: str
    global_agent_id: str
    register_tx_id: str | None
    metadata_tx_ids: dict[str, str] = field(default_factory=dict)


def load_artifact() -> dict[str, Any]:
    """Load the compiled contract artifact (abi + bytecode) checked into
    `hedera/contracts/RIAIdentityRegistry.json`. Raises `Erc8004ConfigError`
    if it's missing -- run `hedera/contracts/compile.py` to (re)generate it."""
    if not CONTRACT_ARTIFACT_PATH.exists():
        raise Erc8004ConfigError(
            f"Compiled contract artifact not found at {CONTRACT_ARTIFACT_PATH}. "
            "Run `python -m hedera.contracts.compile` to generate it (requires "
            "py-solc-x + network access to fetch solc once)."
        )
    with CONTRACT_ARTIFACT_PATH.open() as f:
        return json.load(f)


def build_operator(account_id_str: str, private_key_str: str) -> tuple[AccountId, PrivateKey, Client]:
    """Build an `(AccountId, PrivateKey, Client)` operator triple from raw
    credential strings, disambiguated via `hedera.key_loader.load_private_key`
    (see that module's docstring for why `PrivateKey.from_string()` alone is
    unsafe). Mirrors `hedera/hcs_logger.py`'s `from_env()` construction path
    rather than importing `hedera.wallet.HederaWallet` -- see this module's
    docstring for why."""
    try:
        account_id = AccountId.from_string(account_id_str)
    except Exception as exc:  # pragma: no cover - defensive, SDK-specific
        raise Erc8004ConfigError(f"HEDERA_ACCOUNT_ID is not a valid Hedera account id: {exc}") from exc

    try:
        private_key = load_private_key(account_id_str, private_key_str)
    except KeyLoadError as exc:
        raise Erc8004ConfigError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive, SDK-specific
        raise Erc8004ConfigError(f"HEDERA_PRIVATE_KEY is not a valid Hedera private key: {exc}") from exc

    client = Client.for_testnet()
    client.set_operator(account_id, private_key)
    return account_id, private_key, client


def deploy_registry(
    client: Client,
    private_key: PrivateKey,
    *,
    gas: int = DEFAULT_CREATE_GAS,
) -> RegistryDeployment:
    """Upload `RIAIdentityRegistry`'s bytecode to the Hedera File Service and
    deploy it via the native Smart Contract Service. One-time operation --
    save the returned `contract_id` (e.g. as `ERC8004_REGISTRY_CONTRACT_ID`)
    to reuse it on subsequent runs instead of deploying a second registry.
    """
    artifact = load_artifact()
    # Hedera's own docs (docs.hedera.com/native/smart-contracts/create:
    # "After you have the hex-encoded bytecode... store that on a file")
    # are explicit that the File Service file must hold the HEX-ENCODED
    # bytecode text, which the network decodes itself when the contract is
    # created -- not pre-decoded raw binary. Confirmed the hard way on a
    # real live run: uploading `bytes.fromhex(artifact["bytecode"])` (raw
    # binary) made ContractCreateTransaction fail with
    # ERROR_DECODING_BYTESTRING ("Decoding the smart contract binary to a
    # byte array failed. Check that the input is a valid hex string.") --
    # the network tried to hex-decode bytes that were already binary.
    # `set_contents()` UTF-8-encodes a `str`, so the hex string's
    # characters are what get chunked below, not decoded bytes.
    bytecode_hex = artifact["bytecode"]

    first_chunk, remainder = bytecode_hex[:FIRST_FILE_CHUNK_BYTES], bytecode_hex[FIRST_FILE_CHUNK_BYTES:]

    try:
        file_tx = (
            FileCreateTransaction()
            .set_keys([private_key.public_key()])
            .set_contents(first_chunk)
            .set_file_memo("RIA ERC-8004 Identity Registry bytecode")
        )
        file_tx.transaction_fee = FILE_TRANSACTION_FEE
        file_tx.freeze_with(client)
        file_tx.sign(private_key)
        file_receipt = file_tx.execute(client, validate_status=True)
        file_id: FileId | None = file_receipt.file_id
        if file_id is None:
            raise Erc8004DeployError(f"FileCreateTransaction receipt had no file_id: {file_receipt}")
        logger.info("erc8004: uploaded bytecode file %s (first chunk, %d bytes)", file_id, len(first_chunk))

        if remainder:
            append_tx = FileAppendTransaction().set_file_id(file_id).set_contents(remainder)
            append_tx.transaction_fee = FILE_TRANSACTION_FEE
            append_tx.freeze_with(client)
            append_tx.sign(private_key)
            append_tx.execute_all(client)
            logger.info("erc8004: appended remaining %d bytes of bytecode to %s", len(remainder), file_id)

        contract_tx = (
            ContractCreateTransaction()
            .set_bytecode_file_id(file_id)
            .set_gas(gas)
            .set_admin_key(private_key.public_key())
            .set_contract_memo("RIA ERC-8004 Identity Registry")
        )
        contract_tx.freeze_with(client)
        contract_tx.sign(private_key)
        contract_receipt = contract_tx.execute(client, validate_status=True)
        contract_id: ContractId | None = contract_receipt.contract_id
        if contract_id is None:
            raise Erc8004DeployError(f"ContractCreateTransaction receipt had no contract_id: {contract_receipt}")
        logger.info("erc8004: deployed RIAIdentityRegistry at %s", contract_id)
    except Erc8004DeployError:
        raise
    except Exception as exc:
        raise Erc8004DeployError(f"Failed to deploy RIAIdentityRegistry: {exc}") from exc

    return RegistryDeployment(
        file_id=str(file_id),
        contract_id=str(contract_id),
        contract_evm_address=contract_id.to_evm_address(),
    )


def _agent_count(client: Client, contract_id: ContractId, *, gas: int = 60_000) -> int:
    """Read-only `agentCount()` call, used to determine a just-registered
    agent's id without decoding a state-changing call's return value (see
    the contract's own docstring for why)."""
    result = (
        ContractCallQuery()
        .set_contract_id(contract_id)
        .set_gas(gas)
        .set_function("agentCount")
        .execute(client)
    )
    return result.get_uint256(0)


def build_agent_uri(agent_key: str, *, extra_metadata: dict[str, str] | None = None) -> str:
    """Build a self-contained `data:application/json;base64,...` agentURI
    (RFC 2397) for `agent_key` from `AGENT_TABLE` -- see module docstring
    for why this isn't an HTTP URL. Document shape follows the fields
    ERC-8004's draft text describes for a registration document (`type`,
    `name`, `description`, `services`, `x402Support`, `active`)."""
    if agent_key not in AGENT_TABLE:
        raise Erc8004ConfigError(f"Unknown agent_key {agent_key!r} -- expected one of {sorted(AGENT_TABLE)}")
    info = AGENT_TABLE[agent_key]
    doc = {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration",
        "name": info["name"],
        "description": info["description"],
        "capabilities": info["capabilities"],
        "services": [
            {"type": "a2a-pipeline", "endpoint": f"ria://agents/{agent_key}"},
        ],
        # Only ORACLE actually holds x402 payment authority in RIA's
        # pipeline (see agents/oracle.py and the containment rule in
        # .claude/agents/hedera-payments-engineer.md) -- the other three
        # agents never spend HBAR, so this is false for them, not a
        # blanket "all agents support x402" claim.
        "x402Support": agent_key == "oracle",
        "active": True,
    }
    if extra_metadata:
        doc.update(extra_metadata)
    encoded = base64.b64encode(json.dumps(doc, sort_keys=True).encode()).decode()
    return f"data:application/json;base64,{encoded}"


def register_agent(
    client: Client,
    account_id: AccountId,
    private_key: PrivateKey,
    contract_id: ContractId,
    *,
    agent_key: str,
    agent_uri: str | None = None,
    metadata: dict[str, bytes] | None = None,
    gas: int = DEFAULT_EXECUTE_GAS,
) -> AgentRegistration:
    """Register one agent: `register(string agentURI)` (the agentURI-only
    overload -- see contract docstring for why), then one `setMetadata()`
    call per `metadata` entry. Idempotent in the sense that re-running
    always creates a NEW agent id (the contract has no "already
    registered" check by design -- ERC-8004 identities are meant to be
    freely re-registerable/updatable via `setAgentURI`, not unique per
    owner) -- so callers (e.g. the live script) should track and reuse
    the returned `agent_id` rather than calling this twice for the same
    agent.
    """
    if agent_key not in AGENT_TABLE:
        raise Erc8004ConfigError(f"Unknown agent_key {agent_key!r} -- expected one of {sorted(AGENT_TABLE)}")

    resolved_uri = agent_uri if agent_uri is not None else build_agent_uri(agent_key)

    try:
        before_count = _agent_count(client, contract_id)

        params = ContractFunctionParameters().add_string(resolved_uri)
        tx = ContractExecuteTransaction().set_contract_id(contract_id).set_gas(gas).set_function("register", params)
        tx.transaction_fee = EXECUTE_TRANSACTION_FEE
        tx.freeze_with(client)
        tx.sign(private_key)
        response = tx.execute(client, wait_for_receipt=False)
        receipt = response.get_receipt(client, validate_status=True)
        register_tx_id = str(receipt.transaction_id) if receipt.transaction_id else str(response.transaction_id)

        after_count = _agent_count(client, contract_id)
        if after_count != before_count + 1:
            raise Erc8004RegisterError(
                f"agentCount() went from {before_count} to {after_count} after registering "
                f"{agent_key!r} -- expected exactly +1. Refusing to guess the new agent_id."
            )
        agent_id = after_count
        logger.info("erc8004: registered %s as agent id %d on %s", agent_key, agent_id, contract_id)

        metadata_tx_ids: dict[str, str] = {}
        for key, value in (metadata or {}).items():
            meta_params = (
                ContractFunctionParameters().add_uint256(agent_id).add_string(key).add_bytes(value)
            )
            meta_tx = (
                ContractExecuteTransaction()
                .set_contract_id(contract_id)
                .set_gas(gas)
                .set_function("setMetadata", meta_params)
            )
            meta_tx.transaction_fee = EXECUTE_TRANSACTION_FEE
            meta_tx.freeze_with(client)
            meta_tx.sign(private_key)
            meta_response = meta_tx.execute(client, wait_for_receipt=False)
            meta_receipt = meta_response.get_receipt(client, validate_status=True)
            metadata_tx_ids[key] = (
                str(meta_receipt.transaction_id) if meta_receipt.transaction_id else str(meta_response.transaction_id)
            )
            logger.info("erc8004: set metadata %r on agent %d", key, agent_id)
    except Erc8004RegisterError:
        raise
    except Exception as exc:
        raise Erc8004RegisterError(f"Failed to register agent {agent_key!r}: {exc}") from exc

    # ERC-8004's own global-id example ("eip155:1:0x742...") includes the
    # "0x" prefix on the address component -- to_evm_address() returns
    # bare hex, so it's added here explicitly.
    global_id = f"{HEDERA_TESTNET_CAIP2}:0x{contract_id.to_evm_address()}:{agent_id}"

    return AgentRegistration(
        agent_key=agent_key,
        name=AGENT_TABLE[agent_key]["name"],
        agent_id=agent_id,
        owner_account_id=str(account_id),
        contract_id=str(contract_id),
        agent_uri=resolved_uri,
        global_agent_id=global_id,
        register_tx_id=register_tx_id,
        metadata_tx_ids=metadata_tx_ids,
    )


def verify_agent(client: Client, contract_id: ContractId, agent_id: int, *, gas: int = 60_000) -> dict[str, Any]:
    """Read-only, post-registration confirmation: `ownerOf(agentId)` +
    `tokenURI(agentId)` via `ContractCallQuery` -- no wallet/credentials
    needed beyond a client bound to *some* operator to pay the (tiny)
    query fee. Used by the live script to prove registration really
    landed on-chain, not just that the transaction didn't raise."""
    owner_result = ContractCallQuery().set_contract_id(contract_id).set_gas(gas).set_function(
        "ownerOf", ContractFunctionParameters().add_uint256(agent_id)
    ).execute(client)
    uri_result = ContractCallQuery().set_contract_id(contract_id).set_gas(gas).set_function(
        "tokenURI", ContractFunctionParameters().add_uint256(agent_id)
    ).execute(client)
    return {
        "owner": owner_result.get_address(0),
        "token_uri": uri_result.get_string(0),
    }


__all__ = [
    "AGENT_TABLE",
    "AgentRegistration",
    "CONTRACT_ARTIFACT_PATH",
    "DEFAULT_CREATE_GAS",
    "DEFAULT_EXECUTE_GAS",
    "Erc8004ConfigError",
    "Erc8004DeployError",
    "Erc8004RegisterError",
    "HEDERA_TESTNET_CAIP2",
    "RegistryDeployment",
    "build_agent_uri",
    "build_operator",
    "deploy_registry",
    "load_artifact",
    "register_agent",
    "verify_agent",
]
