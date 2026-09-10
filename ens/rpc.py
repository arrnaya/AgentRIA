"""Minimal Sepolia JSON-RPC client over httpx.

Read access (`eth_call`) and write access (sign locally with eth_account,
then `eth_sendRawTransaction`) for the ENS Registry + Permissioned
Resolver, without depending on web3.py — see requirements.txt for why.
`httpx` is already a project dependency (graph/subgraph_client.py uses it
the same synchronous way for the Graph Gateway).
"""

from __future__ import annotations

import itertools
from typing import Any, Protocol

import httpx

from eth_account.signers.local import LocalAccount

from ens.constants import SEPOLIA_CHAIN_ID

# A single storage-slot text/approval write on Sepolia comfortably fits
# under this; generous on purpose so we don't need a separate
# eth_estimateGas round trip (and thus a bigger mock surface in tests) for
# calls this cheap and predictable.
DEFAULT_GAS = 150_000

_request_ids = itertools.count(1)


class RpcError(RuntimeError):
    """Raised when the RPC node returns a JSON-RPC error object."""


class EthRpc(Protocol):
    """The slice of RPC behaviour resolver.py/register.py depend on —
    lets tests substitute a hand-written fake with no network access."""

    def eth_call(self, to: str, data: bytes) -> bytes: ...
    def get_transaction_count(self, address: str) -> int: ...
    def gas_price(self) -> int: ...
    def send_raw_transaction(self, raw: bytes) -> str: ...


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

    def get_transaction_count(self, address: str) -> int:
        return int(self._request("eth_getTransactionCount", [address, "pending"]), 16)

    def gas_price(self) -> int:
        return int(self._request("eth_gasPrice", []), 16)

    def send_raw_transaction(self, raw: bytes) -> str:
        return self._request("eth_sendRawTransaction", [_hex(raw)])

    def is_connected(self) -> bool:
        try:
            self._request("eth_chainId", [])
            return True
        except Exception:
            return False


def _hex(data: bytes) -> str:
    return "0x" + data.hex()


def build_and_send(rpc: EthRpc, to: str, data: bytes, signer: LocalAccount, value: int = 0) -> str:
    """Build a legacy transaction calling `to` with `data`, sign it with
    `signer`, and broadcast it. Shared by resolver.py and register.py so
    every on-chain write goes through the exact same tx-construction path.

    `value` (wei) is 0 for every contract call here except the one funding
    transfer register.py sends each derived agent account before that
    agent signs its own transaction — see register.py's `FUNDING_WEI`.
    """
    tx = {
        "to": to,
        "data": _hex(data),
        "from": signer.address,
        "nonce": rpc.get_transaction_count(signer.address),
        "chainId": SEPOLIA_CHAIN_ID,
        "gas": DEFAULT_GAS,
        "gasPrice": rpc.gas_price(),
        "value": value,
    }
    signed = signer.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
    return rpc.send_raw_transaction(raw)
