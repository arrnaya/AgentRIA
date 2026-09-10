"""Minimal Sepolia JSON-RPC client over httpx.

Read access (`eth_call`) and write access (sign locally with eth_account,
then `eth_sendRawTransaction`) for the ENS Registry + Permissioned
Resolver, without depending on web3.py — see requirements.txt for why.
`httpx` is already a project dependency (graph/subgraph_client.py uses it
the same synchronous way for the Graph Gateway).
"""

from __future__ import annotations

import itertools
import time
from typing import Any, Protocol

import httpx

from eth_account.signers.local import LocalAccount

from ens.constants import SEPOLIA_CHAIN_ID

# A single storage-slot text/approval write on Sepolia comfortably fits
# under this; generous on purpose so we don't need a separate
# eth_estimateGas round trip (and thus a bigger mock surface in tests) for
# calls this cheap and predictable.
DEFAULT_GAS = 150_000

# How long build_and_send() waits for a transaction to actually be mined
# before giving up, and how often it polls eth_getTransactionReceipt while
# waiting. Sepolia blocks land roughly every ~12s; 3 confirmations of slack
# built into the timeout for a slow block.
RECEIPT_TIMEOUT_S = 180.0
RECEIPT_POLL_INTERVAL_S = 4.0

# eth_gasPrice's own suggestion has been observed going stale fast enough
# on Sepolia to leave a transaction genuinely stuck (confirmed in practice:
# a transaction sent at the node's then-current suggested price sat
# unconfirmed for 180s+ while the network's price had already moved up
# ~7%). A modest buffer costs nothing on a testnet and meaningfully lowers
# the odds of landing underpriced.
GAS_PRICE_BUFFER = 1.25

# If a transaction still hasn't confirmed after RECEIPT_TIMEOUT_S, resend
# it at the same nonce with a bumped price rather than just giving up --
# most nodes require at least ~10% over the original to accept a
# replacement; this multiplies the *original* price each retry, not the
# network's (possibly still-stale) current suggestion.
TIMEOUT_REBROADCAST_RETRIES = 2
TIMEOUT_REBROADCAST_BUMP = 1.5

# Some providers (confirmed against Infura in practice, 2026-09) cap how
# many unconfirmed transactions they'll accept from one sender at once and
# reject anything past it with this message rather than a normal nonce/gas
# error. build_and_send() waiting for each transaction's receipt before
# returning is the real fix (it keeps exactly one transaction in flight per
# signer at a time) -- this retry is a backstop for the send call itself,
# in case the limit is still hit transiently (e.g. a stale pending tx from
# outside this process).
_IN_FLIGHT_LIMIT_RETRIES = 5
_IN_FLIGHT_LIMIT_BACKOFF_S = 6.0

_request_ids = itertools.count(1)


class RpcError(RuntimeError):
    """Raised when the RPC node returns a JSON-RPC error object."""


class TransactionRevertedError(RuntimeError):
    """Raised when a transaction was mined but its receipt reports failure
    (status 0) -- broadcasting succeeded, executing on-chain didn't."""


class EthRpc(Protocol):
    """The slice of RPC behaviour resolver.py/register.py depend on —
    lets tests substitute a hand-written fake with no network access."""

    def eth_call(self, to: str, data: bytes) -> bytes: ...
    def get_transaction_count(self, address: str) -> int: ...
    def gas_price(self) -> int: ...
    def send_raw_transaction(self, raw: bytes) -> str: ...
    def get_code(self, address: str) -> bytes: ...
    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any] | None: ...


class SepoliaRpcClient:
    """Thin synchronous JSON-RPC client for one Sepolia endpoint."""

    def __init__(self, rpc_url: str, timeout_s: float = 20.0):
        self.rpc_url = rpc_url
        self.timeout_s = timeout_s

    def _request(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": next(_request_ids), "method": method, "params": params}
        response = httpx.post(self.rpc_url, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RpcError(f"{method} failed: {body['error']}")
        return body["result"]

    def eth_call(self, to: str, data: bytes) -> bytes:
        result = self._request("eth_call", [{"to": to, "data": _hex(data)}, "latest"])
        return bytes.fromhex(result[2:])

    def get_transaction_count(self, address: str, block: str = "pending") -> int:
        return int(self._request("eth_getTransactionCount", [address, block]), 16)

    def gas_price(self) -> int:
        return int(self._request("eth_gasPrice", []), 16)

    def send_raw_transaction(self, raw: bytes) -> str:
        return self._request("eth_sendRawTransaction", [_hex(raw)])

    def get_code(self, address: str) -> bytes:
        result = self._request("eth_getCode", [address, "latest"])
        return bytes.fromhex(result[2:])

    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        return self._request("eth_getTransactionReceipt", [tx_hash])

    def is_connected(self) -> bool:
        try:
            self._request("eth_chainId", [])
            return True
        except Exception:
            return False


def _hex(data: bytes) -> str:
    return "0x" + data.hex()


def _is_in_flight_limit_error(exc: Exception) -> bool:
    return "in-flight transaction limit" in str(exc).lower()


def wait_for_receipt(
    rpc: EthRpc,
    tx_hash: str,
    *,
    timeout_s: float = RECEIPT_TIMEOUT_S,
    poll_interval_s: float = RECEIPT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll eth_getTransactionReceipt until `tx_hash` is mined.

    Raises TimeoutError if it never confirms within `timeout_s`, or
    TransactionRevertedError if it's mined but the receipt's `status` is
    0x0 (reverted on-chain -- broadcast succeeded, execution didn't).
    """
    deadline = time.monotonic() + timeout_s
    while True:
        receipt = rpc.get_transaction_receipt(tx_hash)
        if receipt is not None:
            status = receipt.get("status")
            if status in (0, "0x0"):
                raise TransactionRevertedError(
                    f"Transaction {tx_hash} was mined but reverted (status 0). "
                    f"Receipt: {receipt}"
                )
            return receipt
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Transaction {tx_hash} was not mined within {timeout_s:.0f}s. "
                "It may still confirm later -- check on Sepolia before retrying "
                "the operation that sent it, to avoid double-sending."
            )
        time.sleep(poll_interval_s)


def build_and_send(
    rpc: EthRpc,
    to: str,
    data: bytes,
    signer: LocalAccount,
    value: int = 0,
    *,
    nonce: int | None = None,
    gas_price_multiplier: float = 1.0,
) -> str:
    """Build a legacy transaction calling `to` with `data`, sign it with
    `signer`, broadcast it, and block until it's actually mined. Shared by
    resolver.py, register.py, registry.py and factory.py so every on-chain
    write goes through the exact same tx-construction path.

    Waiting for the receipt here (rather than returning immediately after
    broadcast) is deliberate, not just cautious: register_all() sends
    several dependent writes from the same signer back-to-back (deploy a
    proxy, then point a name at it, then authorize an agent, then fund it,
    then that agent writes its own records) and some RPC providers
    (confirmed against Infura in practice) reject a new transaction from an
    address that already has one unconfirmed, with a policy error rather
    than a normal nonce/gas one. Waiting for each transaction to land
    before sending the next keeps exactly one in flight per signer, which
    avoids that class of failure entirely rather than working around it.

    `value` (wei) is 0 for every contract call here except the one funding
    transfer register.py sends each derived agent account before that
    agent signs its own transaction — see register.py's `FUNDING_WEI`.

    `nonce`, if given, is used as-is instead of looked up live -- the one
    caller that needs this is scripts/register_agents_live.py's stuck-nonce
    pre-flight check, replacing a specific already-pending transaction
    rather than sending the next one in sequence. `gas_price_multiplier`
    stacks on top of `GAS_PRICE_BUFFER` for the same case: a stuck
    transaction from a *previous process* needs a price confidently above
    whatever it was sent at, which this process never saw.
    """
    if nonce is None:
        nonce = rpc.get_transaction_count(signer.address)
    gas_price = round(rpc.gas_price() * GAS_PRICE_BUFFER * gas_price_multiplier)

    for rebroadcast in range(TIMEOUT_REBROADCAST_RETRIES + 1):
        tx = {
            "to": to,
            "data": _hex(data),
            "from": signer.address,
            "nonce": nonce,
            "chainId": SEPOLIA_CHAIN_ID,
            "gas": DEFAULT_GAS,
            "gasPrice": gas_price,
            "value": value,
        }
        signed = signer.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)

        tx_hash = _send_with_in_flight_retry(rpc, raw)

        try:
            wait_for_receipt(rpc, tx_hash)
            return tx_hash
        except TimeoutError:
            if rebroadcast == TIMEOUT_REBROADCAST_RETRIES:
                raise
            gas_price = round(gas_price * TIMEOUT_REBROADCAST_BUMP)
            # Same nonce, higher price: a standard replace-by-fee resend,
            # not a new/duplicate action -- the original stays pending
            # until one of the two lands, so this never double-executes.

    raise AssertionError("unreachable")  # pragma: no cover -- loop always returns or raises


def _send_with_in_flight_retry(rpc: EthRpc, raw: bytes) -> str:
    """send_raw_transaction, retrying a few times with backoff if the
    provider rejects it with an in-flight-transaction-limit policy error
    (see module docstring) rather than a normal nonce/gas problem."""
    last_exc: Exception | None = None
    for attempt in range(_IN_FLIGHT_LIMIT_RETRIES):
        try:
            return rpc.send_raw_transaction(raw)
        except RpcError as exc:
            if not _is_in_flight_limit_error(exc) or attempt == _IN_FLIGHT_LIMIT_RETRIES - 1:
                raise
            last_exc = exc
            time.sleep(_IN_FLIGHT_LIMIT_BACKOFF_S)
    raise last_exc or RpcError("send_raw_transaction never returned a hash")  # pragma: no cover
