"""Minimal Solidity ABI encoding for the handful of functions RIA calls.

Deliberately not using web3.py's Contract abstraction — see
requirements.txt for why (its own PyPI wheel ships a top-level `ens`
package that collides with this directory). This does the same job
web3.py's Contract class does underneath: compute a 4-byte selector from
the canonical function signature, then encode/decode arguments with
eth_abi — just spelled out directly for the ~9 functions we need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_utils import keccak


@dataclass(frozen=True)
class Function:
    """One Solidity function: enough to build calldata and decode a result."""

    name: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...] = ()

    @property
    def signature(self) -> str:
        return f"{self.name}({','.join(self.input_types)})"

    @property
    def selector(self) -> bytes:
        return keccak(text=self.signature)[:4]

    def encode_call(self, *args: Any) -> bytes:
        """4-byte selector + ABI-encoded args, ready to use as tx `data`."""
        return self.selector + abi_encode(list(self.input_types), list(args))

    def decode_output(self, data: bytes) -> tuple[Any, ...]:
        """Decode raw return data (e.g. from `eth_call`) per output_types."""
        return abi_decode(list(self.output_types), data)
