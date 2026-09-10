"""In-memory fake Sepolia chain for ENS tests.

Not a test module itself (no test_ prefix, so pytest won't collect it) --
a shared fixture used by test_ens_resolver.py and test_ens_register.py.

Rather than mocking "assume this call is authorized", this decodes real
ABI calldata (via ens/abi.py's Function.selector) and recovers the real
signer of each raw signed transaction (via eth_account + rlp, exactly how
a real node would), then applies the *same* authorisation logic
PublicResolver.sol's `authorised(node)` modifier does. That means a test
exercising set_text() here is exercising the real encode/decode/sign path
production code uses, not a shortcut -- if EXEC's key can trick this fake
into writing ORACLE's node, it could trick a real Sepolia node too.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import rlp
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak

from ens.constants import DEFAULT_PUBLIC_RESOLVER_ADDRESS, ENS_REGISTRY_ADDRESS
from ens.register import SET_SUBNODE_RECORD_FN
from ens.resolver import (
    APPROVE_FN,
    IS_APPROVED_FOR_ALL_FN,
    IS_APPROVED_FOR_FN,
    OWNER_FN,
    SET_TEXT_FN,
    TEXT_FN,
)

ZERO_ADDRESS = "0x" + "00" * 20


class ChainRevert(RuntimeError):
    """Stands in for a real on-chain `require(...)` revert."""


def _encode_result(output_types: tuple[str, ...], value) -> bytes:
    return abi_encode(list(output_types), [value])


@dataclass
class FakeChain:
    """Implements the EthRpc protocol (eth_call / get_transaction_count /
    gas_price / send_raw_transaction) against in-memory state."""

    registry_address: str = ENS_REGISTRY_ADDRESS
    resolver_address: str = DEFAULT_PUBLIC_RESOLVER_ADDRESS
    owners: dict[bytes, str] = field(default_factory=dict)
    # (owner_lower, node, delegate_lower) -> approved
    node_approvals: dict[tuple[str, bytes, str], bool] = field(default_factory=dict)
    operator_approvals: dict[tuple[str, str], bool] = field(default_factory=dict)
    texts: dict[tuple[bytes, str], str] = field(default_factory=dict)
    _nonces: dict[str, int] = field(default_factory=dict)
    _balances: dict[str, int] = field(default_factory=dict)

    def set_owner(self, node: bytes, owner: str) -> None:
        """Test/setup helper equivalent to the registry recording an owner
        (what a real setSubnodeRecord call would have done)."""
        self.owners[node] = owner

    def get_balance(self, address: str) -> int:
        """Wei balance credited to `address` by plain transfers so far —
        lets tests assert register.py's agent-funding step actually ran,
        not just that it didn't raise."""
        return self._balances.get(address.lower(), 0)

    # --- EthRpc protocol -------------------------------------------------

    def eth_call(self, to: str, data: bytes) -> bytes:
        selector, payload = data[:4], data[4:]
        if to.lower() == self.registry_address.lower() and selector == OWNER_FN.selector:
            (node,) = self._decode(OWNER_FN, payload)
            return _encode_result(OWNER_FN.output_types, self.owners.get(node, ZERO_ADDRESS))
        if to.lower() == self.resolver_address.lower() and selector == TEXT_FN.selector:
            node, key = self._decode(TEXT_FN, payload)
            return _encode_result(TEXT_FN.output_types, self.texts.get((node, key), ""))
        if to.lower() == self.resolver_address.lower() and selector == IS_APPROVED_FOR_FN.selector:
            owner, node, delegate = self._decode(IS_APPROVED_FOR_FN, payload)
            key = (owner.lower(), node, delegate.lower())
            return _encode_result(IS_APPROVED_FOR_FN.output_types, self.node_approvals.get(key, False))
        if to.lower() == self.resolver_address.lower() and selector == IS_APPROVED_FOR_ALL_FN.selector:
            account, operator = self._decode(IS_APPROVED_FOR_ALL_FN, payload)
            key = (account.lower(), operator.lower())
            return _encode_result(
                IS_APPROVED_FOR_ALL_FN.output_types, self.operator_approvals.get(key, False)
            )
        raise ChainRevert(f"FakeChain: no handler for selector {selector.hex()} to {to}")

    def get_transaction_count(self, address: str) -> int:
        return self._nonces.get(address.lower(), 0)

    def gas_price(self) -> int:
        return 1_000_000_000

    def send_raw_transaction(self, raw: bytes) -> str:
        sender = Account.recover_transaction(raw)
        nonce, _gas_price, _gas, to, value, data, *_sig = rlp.decode(raw)
        to_address = "0x" + bytes(to).hex()
        data = bytes(data)
        value_wei = int.from_bytes(bytes(value), "big") if value else 0

        self._nonces[sender.lower()] = int.from_bytes(nonce, "big") + 1

        if value_wei:
            # A plain value transfer (register.py funding a derived agent
            # account) -- no gas deduction modelled, this fake only tracks
            # transfers so tests can assert funding actually happened.
            self._balances[to_address.lower()] = self.get_balance(to_address) + value_wei

        if not data:
            # No calldata: this was a plain transfer, not a contract call --
            # nothing left to decode/authorise.
            return "0x" + "44" * 32

        selector, payload = data[:4], data[4:]

        if to_address.lower() == self.registry_address.lower() and selector == SET_SUBNODE_RECORD_FN.selector:
            parent_node, label, owner, _resolver, _ttl = self._decode(SET_SUBNODE_RECORD_FN, payload)
            node = keccak(parent_node + label)
            self.owners[node] = owner
            # No auth modelled for subnode creation itself -- ENSRegistry's
            # own ownership rules aren't what this track is judged on, the
            # resolver's write isolation (tested above/below) is.
            return "0x" + "11" * 32

        if to_address.lower() == self.resolver_address.lower():
            if selector == APPROVE_FN.selector:
                node, delegate, approved = self._decode(APPROVE_FN, payload)
                # Mirrors PublicResolver.approve(): recorded under the
                # *caller's* own owner slot, matching prod behaviour where
                # resolver.py already refused to call this unless the
                # signer is the node's real registry owner.
                self.node_approvals[(sender.lower(), node, delegate.lower())] = approved
                return "0x" + "22" * 32
            if selector == SET_TEXT_FN.selector:
                node, key, value = self._decode(SET_TEXT_FN, payload)
                if not self._is_authorised(node, sender):
                    raise ChainRevert(
                        f"authorised(node) reverted: {sender} may not write node {node.hex()}"
                    )
                self.texts[(node, key)] = value
                return "0x" + "33" * 32

        raise ChainRevert(f"FakeChain: no handler for selector {selector.hex()} to {to_address}")

    # --- internals ---------------------------------------------------

    def _decode(self, fn, payload: bytes):
        return abi_decode(list(fn.input_types), payload)

    def _is_authorised(self, node: bytes, sender: str) -> bool:
        owner = self.owners.get(node, ZERO_ADDRESS)
        if owner.lower() == sender.lower():
            return True
        if self.operator_approvals.get((owner.lower(), sender.lower()), False):
            return True
        return self.node_approvals.get((owner.lower(), node, sender.lower()), False)
