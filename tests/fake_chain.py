"""In-memory fake Sepolia chain for ENS tests.

Not a test module itself (no test_ prefix, so pytest won't collect it) --
a shared fixture used by test_ens_resolver.py and test_ens_register.py.

Rather than mocking "assume this call is authorized", this decodes real
ABI calldata (via ens/abi.py's Function.selector) and recovers the real
signer of each raw signed transaction (via eth_account + rlp, exactly how
a real node would), then applies the *same* Enhanced Access Control (EAC)
logic PermissionedResolver.sol's `onlyPartRoles` modifier and
PermissionedRegistry.sol's role checks do (ens/eac.py, shared with the
production client-side checks in ens/resolver.py). That means a test
exercising set_text()/authorize_agent() here is exercising the real
encode/decode/sign path production code uses, not a shortcut -- if EXEC's
key can trick this fake into writing ORACLE's node, it could trick a real
Sepolia node too.

This models ENSv2's *hierarchical* registry shape (multiple independently
deployed PermissionedRegistry/PermissionedResolver instances, plus
VerifiableFactory's CREATE2 proxy deployment), not ENSv1's single flat
registry -- see ens/registry.py, ens/resolver.py and ens/factory.py's
module docstrings for what's verified against the real, currently-deployed
contract source (and live on-chain state) each piece mirrors.

One deliberate simplification: real PermissionedRegistry entries carry
`eacVersionId`/`tokenVersionId` version bits that get bumped on
unregister/role-regeneration (see PermissionedRegistry.sol's
_constructResource); this fake never unregisters or regenerates a token,
so it always treats a label's EAC resource as plain `label_id(label)`
(version 0) -- correct for every scenario these tests exercise. Likewise,
VerifiableFactory's real CREATE2 address is `Create2.computeAddress(...)`
over an exact clone-bytecode template; this fake predicts a pseudo-address
via `keccak(sender, salt, implementation)` instead. Neither production
code path (ens/factory.py, ens/registry.py, ens/resolver.py) ever depends
on the specific *bytes* of an address -- only on addresses being
deterministic given their inputs and colliding on redeploy -- so this
substitution doesn't change what's being tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import rlp
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from ens.constants import (
    ENS_ETH_REGISTRY_ADDRESS,
    ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS,
    ENS_USER_REGISTRY_IMPL_ADDRESS,
    ENS_VERIFIABLE_FACTORY_ADDRESS,
    ROLE_REGISTRAR,
    ROLE_SET_RESOLVER,
    ROLE_SET_RESOLVER_ADMIN,
    ROLE_SET_SUBREGISTRY,
    ROLE_SET_SUBREGISTRY_ADMIN,
    ROLE_SET_TEXT,
)
from ens.eac import ROOT_RESOURCE, can_grant_roles, has_roles
from ens.factory import DEPLOY_PROXY_FN
from ens.registry import (
    FIND_OWNER_FN,
    GET_EXPIRY_FN,
    GET_RESOLVER_FN,
    GET_SUBREGISTRY_FN,
    REGISTER_FN,
    ROLES_FN,
    SET_SUBREGISTRY_FN,
    USER_REGISTRY_INITIALIZE_FN,
    ZERO_ADDRESS,
)
from ens.resolver import AUTHORIZE_NAME_ROLES_FN, INITIALIZE_FN, SET_TEXT_FN, TEXT_FN, resource

ZERO_NODE = b"\x00" * 32
# An unrelated resolver address, standing in for the small, unrelated
# resolver contract agentria.eth's own top-level name actually resolves
# through on-chain today -- confirmed distinct from
# ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS, see ens/registry.py's citation.
AGENTRIA_OWN_RESOLVER = "0x" + "cc" * 20


class ChainRevert(RuntimeError):
    """Stands in for a real on-chain `require(...)` / EAC revert."""


def _encode_result(output_types: tuple[str, ...], value) -> bytes:
    return abi_encode(list(output_types), [value])


@dataclass
class _Entry:
    owner: str
    subregistry: str
    resolver: str
    expiry: int


@dataclass
class _RegistryState:
    """One deployed PermissionedRegistry (or UserRegistry proxy)
    instance's state: its labels and its EAC roles."""

    entries: dict[str, _Entry] = field(default_factory=dict)
    roles: dict[tuple[int, str], int] = field(default_factory=dict)


@dataclass
class _ResolverState:
    """One deployed PermissionedResolver proxy instance's state: its text
    records and its EAC roles."""

    texts: dict[tuple[bytes, str], str] = field(default_factory=dict)
    roles: dict[tuple[int, str], int] = field(default_factory=dict)


@dataclass
class FakeChain:
    """Implements the EthRpc protocol (eth_call / get_transaction_count /
    gas_price / send_raw_transaction / get_code) against in-memory state
    modelling ENSv2's hierarchical registries + resolvers + factory."""

    factory_address: str = ENS_VERIFIABLE_FACTORY_ADDRESS
    user_registry_impl: str = ENS_USER_REGISTRY_IMPL_ADDRESS
    permissioned_resolver_impl: str = ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS
    registries: dict[str, _RegistryState] = field(default_factory=dict)
    resolvers: dict[str, _ResolverState] = field(default_factory=dict)
    _nonces: dict[str, int] = field(default_factory=dict)
    _balances: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # The root .eth registry always exists.
        self.registries[ENS_ETH_REGISTRY_ADDRESS.lower()] = _RegistryState()

    # --- test setup helpers ----------------------------------------------

    def seed_agentria(self, admin_address: str, *, expiry: int) -> None:
        """Mirrors the real, already-registered on-chain state of
        agentria.eth: owned by `admin_address`, resolved through some
        unrelated resolver, no subregistry yet -- plus the registry-level
        roles ETHRegistrar's REGISTRATION_ROLE_BITMAP grants a name's
        registrant (ROLE_SET_SUBREGISTRY[+admin], ROLE_SET_RESOLVER[+admin]),
        which register.py's ensure_subregistry() needs to attach a new
        subregistry."""
        root = self.registries[ENS_ETH_REGISTRY_ADDRESS.lower()]
        root.entries["agentria"] = _Entry(
            owner=admin_address, subregistry=ZERO_ADDRESS, resolver=AGENTRIA_OWN_RESOLVER, expiry=expiry
        )
        label_resource = _label_id("agentria")
        self._grant(root.roles, label_resource, ROLE_SET_SUBREGISTRY | ROLE_SET_SUBREGISTRY_ADMIN, admin_address)
        self._grant(root.roles, label_resource, ROLE_SET_RESOLVER | ROLE_SET_RESOLVER_ADMIN, admin_address)

    def get_balance(self, address: str) -> int:
        """Wei balance credited to `address` by plain transfers so far —
        lets tests assert register.py's agent-funding step actually ran,
        not just that it didn't raise."""
        return self._balances.get(address.lower(), 0)

    # --- EthRpc protocol -------------------------------------------------

    def eth_call(self, to: str, data: bytes) -> bytes:
        to_lower = to.lower()
        selector, payload = data[:4], data[4:]

        if to_lower == self.factory_address.lower() and selector == DEPLOY_PROXY_FN.selector:
            implementation, salt, _init_data = self._decode(DEPLOY_PROXY_FN, payload)
            # Simulate only: predict the address, touch no state. Reverts
            # (like a real create2-to-existing-code failure) if this
            # exact (implementation, salt) is already deployed -- the
            # caller doesn't know *who* msg.sender is under eth_call, so
            # this fake keys purely on (implementation, salt), which is
            # sufficient for every test scenario here (one admin key).
            predicted = _predict_proxy_address(implementation, salt)
            if predicted.lower() in self.registries or predicted.lower() in self.resolvers:
                raise ChainRevert(f"FakeChain: {predicted} already deployed (redeploy of same salt)")
            return _encode_result(DEPLOY_PROXY_FN.output_types, predicted)

        if to_lower in self.registries:
            return self._registry_eth_call(to_lower, selector, payload)

        if to_lower in self.resolvers:
            return self._resolver_eth_call(to_lower, selector, payload)

        raise ChainRevert(f"FakeChain: no handler for selector {selector.hex()} to {to}")

    def get_transaction_count(self, address: str) -> int:
        return self._nonces.get(address.lower(), 0)

    def get_transaction_receipt(self, tx_hash: str) -> dict[str, str] | None:
        # send_raw_transaction executes synchronously and raises (rather
        # than returning a hash) on any on-chain-style failure -- so any
        # hash this fake ever handed back already represents a mined,
        # successful transaction. "Mined on the very first poll" is a
        # faithful enough model of that for ens/rpc.py's wait_for_receipt()
        # to exercise the same code path tests already cover, without this
        # fake needing to simulate confirmation delay.
        return {"status": "0x1", "transactionHash": tx_hash, "blockNumber": "0x1"}

    def gas_price(self) -> int:
        return 1_000_000_000

    def get_code(self, address: str) -> bytes:
        address = address.lower()
        if (
            address in self.registries
            or address in self.resolvers
            or address in (self.factory_address.lower(), self.user_registry_impl.lower(), self.permissioned_resolver_impl.lower())
        ):
            return b"\x60\x80\x60\x40"  # non-empty stand-in bytecode
        return b""

    def send_raw_transaction(self, raw: bytes) -> str:
        sender = Account.recover_transaction(raw)
        nonce, _gas_price, _gas, to, value, data, *_sig = rlp.decode(raw)
        to_address = "0x" + bytes(to).hex()
        to_lower = to_address.lower()
        data = bytes(data)
        value_wei = int.from_bytes(bytes(value), "big") if value else 0

        self._nonces[sender.lower()] = int.from_bytes(nonce, "big") + 1

        if value_wei:
            # A plain value transfer (register.py funding a derived agent
            # account) -- no gas deduction modelled, this fake only tracks
            # transfers so tests can assert funding actually happened.
            self._balances[to_lower] = self.get_balance(to_address) + value_wei

        if not data:
            # No calldata: this was a plain transfer, nothing left to
            # decode/authorise.
            return "0x" + "44" * 32

        selector, payload = data[:4], data[4:]

        if to_lower == self.factory_address.lower() and selector == DEPLOY_PROXY_FN.selector:
            return self._deploy_proxy(sender, payload)

        if to_lower in self.registries:
            return self._registry_send(to_lower, sender, selector, payload)

        if to_lower in self.resolvers:
            return self._resolver_send(to_lower, sender, selector, payload)

        raise ChainRevert(f"FakeChain: no handler for selector {selector.hex()} to {to_address}")

    # --- factory -----------------------------------------------------

    def _deploy_proxy(self, sender: str, payload: bytes) -> str:
        implementation, salt, init_data = self._decode(DEPLOY_PROXY_FN, payload)
        predicted = _predict_proxy_address(implementation, salt)
        predicted_lower = predicted.lower()
        if predicted_lower in self.registries or predicted_lower in self.resolvers:
            raise ChainRevert(f"FakeChain: create2 to {predicted} failed, target already has code")

        # `init_data` is delegatecalled as-is (see ens/factory.py's module
        # docstring), so -- exactly like every other calldata this fake
        # decodes -- it carries its own 4-byte function selector first.
        init_payload = init_data[4:]

        if implementation.lower() == self.user_registry_impl.lower():
            state = _RegistryState()
            self.registries[predicted_lower] = state
            root_account, role_bitmap = self._decode(USER_REGISTRY_INITIALIZE_FN, init_payload)
            self._grant(state.roles, ROOT_RESOURCE, role_bitmap, root_account)
        elif implementation.lower() == self.permissioned_resolver_impl.lower():
            state = _ResolverState()
            self.resolvers[predicted_lower] = state
            admin, role_bitmap, _setters = self._decode(INITIALIZE_FN, init_payload)
            self._grant(state.roles, ROOT_RESOURCE, role_bitmap, admin)
        else:
            raise ChainRevert(f"FakeChain: unknown implementation {implementation}")

        return "0x" + "55" * 32

    # --- registry (shared by root .eth registry + any subregistry) ----

    def _registry_eth_call(self, to_lower: str, selector: bytes, payload: bytes) -> bytes:
        state = self.registries[to_lower]
        if selector == FIND_OWNER_FN.selector:
            (label,) = self._decode(FIND_OWNER_FN, payload)
            entry = state.entries.get(label)
            return _encode_result(FIND_OWNER_FN.output_types, entry.owner if entry else ZERO_ADDRESS)
        if selector == GET_SUBREGISTRY_FN.selector:
            (label,) = self._decode(GET_SUBREGISTRY_FN, payload)
            entry = state.entries.get(label)
            return _encode_result(GET_SUBREGISTRY_FN.output_types, entry.subregistry if entry else ZERO_ADDRESS)
        if selector == GET_RESOLVER_FN.selector:
            (label,) = self._decode(GET_RESOLVER_FN, payload)
            entry = state.entries.get(label)
            return _encode_result(GET_RESOLVER_FN.output_types, entry.resolver if entry else ZERO_ADDRESS)
        if selector == GET_EXPIRY_FN.selector:
            (any_id,) = self._decode(GET_EXPIRY_FN, payload)
            label = _label_for_id(state, any_id)
            entry = state.entries.get(label) if label else None
            return _encode_result(GET_EXPIRY_FN.output_types, entry.expiry if entry else 0)
        if selector == ROLES_FN.selector:
            resource_id, account = self._decode(ROLES_FN, payload)
            bitmap = state.roles.get((resource_id, account.lower()), 0)
            return _encode_result(ROLES_FN.output_types, bitmap)
        raise ChainRevert(f"FakeChain: no registry handler for selector {selector.hex()}")

    def _registry_send(self, to_lower: str, sender: str, selector: bytes, payload: bytes) -> str:
        state = self.registries[to_lower]
        if selector == REGISTER_FN.selector:
            label, owner, subregistry_addr, resolver_addr, role_bitmap, expiry = self._decode(
                REGISTER_FN, payload
            )
            if label in state.entries:
                raise ChainRevert(f"FakeChain: label {label!r} already registered")
            if not has_roles(state.roles, ROOT_RESOURCE, ROLE_REGISTRAR, sender):
                raise ChainRevert(
                    f"EACUnauthorizedAccountRoles: {sender} lacks ROLE_REGISTRAR at ROOT_RESOURCE"
                )
            state.entries[label] = _Entry(
                owner=owner, subregistry=subregistry_addr, resolver=resolver_addr, expiry=expiry
            )
            if role_bitmap and owner.lower() != ZERO_ADDRESS.lower():
                self._grant(state.roles, _label_id(label), role_bitmap, owner)
            return "0x" + "11" * 32

        if selector == SET_SUBREGISTRY_FN.selector:
            any_id, new_subregistry = self._decode(SET_SUBREGISTRY_FN, payload)
            label = _label_for_id(state, any_id)
            if label is None or label not in state.entries:
                raise ChainRevert("FakeChain: setSubregistry on unknown label")
            if not has_roles(state.roles, any_id, ROLE_SET_SUBREGISTRY, sender):
                raise ChainRevert(
                    f"EACUnauthorizedAccountRoles: {sender} lacks ROLE_SET_SUBREGISTRY on {label!r}"
                )
            state.entries[label].subregistry = new_subregistry
            return "0x" + "22" * 32

        raise ChainRevert(f"FakeChain: no registry handler for selector {selector.hex()}")

    # --- resolver ------------------------------------------------------

    def _resolver_eth_call(self, to_lower: str, selector: bytes, payload: bytes) -> bytes:
        state = self.resolvers[to_lower]
        if selector == TEXT_FN.selector:
            node, key = self._decode(TEXT_FN, payload)
            return _encode_result(TEXT_FN.output_types, state.texts.get((node, key), ""))
        if selector == ROLES_FN.selector:
            resource_id, account = self._decode(ROLES_FN, payload)
            bitmap = state.roles.get((resource_id, account.lower()), 0)
            return _encode_result(ROLES_FN.output_types, bitmap)
        raise ChainRevert(f"FakeChain: no resolver handler for selector {selector.hex()}")

    def _resolver_send(self, to_lower: str, sender: str, selector: bytes, payload: bytes) -> str:
        state = self.resolvers[to_lower]
        if selector == SET_TEXT_FN.selector:
            node, key, value = self._decode(SET_TEXT_FN, payload)
            # Mirrors PermissionedResolver.onlyPartRoles's node-wide
            # branch: caller must hold ROLE_SET_TEXT on resource(node, 0)
            # (or via ROOT_RESOURCE) -- the only grant shape
            # authorize_agent() ever produces.
            node_resource = resource(node)
            if not has_roles(state.roles, node_resource, ROLE_SET_TEXT, sender):
                raise ChainRevert(
                    f"EACUnauthorizedAccountRoles: {sender} may not write node {node.hex()}"
                )
            state.texts[(node, key)] = value
            return "0x" + "33" * 32

        if selector == AUTHORIZE_NAME_ROLES_FN.selector:
            dns_name, role_bitmap, account, grant = self._decode(AUTHORIZE_NAME_ROLES_FN, payload)
            node_resource = resource(_dns_namehash(dns_name))
            if not can_grant_roles(state.roles, node_resource, role_bitmap, sender):
                raise ChainRevert(
                    f"EACCannotGrantRoles: {sender} cannot grant {role_bitmap} on resource {node_resource}"
                )
            if grant:
                self._grant(state.roles, node_resource, role_bitmap, account)
            else:
                self._revoke(state.roles, node_resource, role_bitmap, account)
            return "0x" + "66" * 32

        raise ChainRevert(f"FakeChain: no resolver handler for selector {selector.hex()}")

    # --- internals ---------------------------------------------------

    def _decode(self, fn, payload: bytes):
        return abi_decode(list(fn.input_types), payload)

    def _grant(self, roles: dict[tuple[int, str], int], resource_id: int, bitmap: int, account: str) -> None:
        key = (resource_id, account.lower())
        roles[key] = roles.get(key, 0) | bitmap

    def _revoke(self, roles: dict[tuple[int, str], int], resource_id: int, bitmap: int, account: str) -> None:
        key = (resource_id, account.lower())
        roles[key] = roles.get(key, 0) & ~bitmap


def _label_id(label: str) -> int:
    return int.from_bytes(keccak(text=label), "big")


def _label_for_id(state: _RegistryState, any_id: int) -> str | None:
    for label in state.entries:
        if _label_id(label) == any_id:
            return label
    return None


def _predict_proxy_address(implementation: str, salt: int) -> str:
    """Pseudo-CREATE2 address, deterministic given (implementation, salt)
    -- see module docstring for why this doesn't need to match real
    VerifiableFactory bytecode math."""
    raw = keccak(
        bytes.fromhex(implementation[2:].rjust(40, "0")) + salt.to_bytes(32, "big")
    )
    return to_checksum_address("0x" + raw[-20:].hex())


def _dns_namehash(dns_name: bytes) -> bytes:
    """Recompute the EIP-137 namehash from a DNS-wire-encoded name, the
    same value NameCoder.namehash(toName, 0) would produce on-chain --
    used here only so the fake's resource() keys line up with the
    bytes32 node setText()/text() use, without importing ens/dns_name.py's
    encoder in reverse."""
    labels: list[bytes] = []
    i = 0
    while dns_name[i] != 0:
        length = dns_name[i]
        labels.append(dns_name[i + 1 : i + 1 + length])
        i += 1 + length
    node = ZERO_NODE
    for label in reversed(labels):
        node = keccak(node + keccak(label))
    return node
