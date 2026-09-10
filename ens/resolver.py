"""Permissioned Resolver interactions — RIA's real per-agent write isolation.

This is the piece the ENS bonus track is actually judged on: EXEC's key
must not be able to overwrite ORACLE's ENS text records, and that has to
be enforced *by the resolver contract itself*, not just by RIA's own code
being polite about which `agent_id` string it passes around.

The mechanism (verified against the real, currently-deployed
contracts/resolvers/PublicResolver.sol in ensdomains/ens-contracts): every
node (one per subname) tracks its own `approve(node, delegate, approved)`
grants, keyed by whoever the ENS Registry actually records as that node's
owner. `setText` is gated by an on-chain `authorised(node)` check
equivalent to:

    msg.sender == registryOwner(node)
    or isApprovedForAll(registryOwner(node), msg.sender)
    or isApprovedFor(registryOwner(node), node, msg.sender)

register.py (as the registry owner / admin) grants exactly one delegate —
that agent's own derived address, see accounts.py — per node, and never
grants any address approval on a node it doesn't own. If EXEC's derived
key calls setText on ORACLE's node, none of the three conditions above can
be true, and the contract's `authorised` modifier reverts the transaction.
That's real, on-chain enforcement, independent of anything in this file.

The client-side check in `is_approved`/`set_text` below is *defense in
depth* — it fails fast with a clear Python exception instead of spending
gas on a transaction that would revert anyway. It is deliberately built to
mirror the on-chain check exactly (same three conditions) rather than
invent a separate, weaker convention.

ENSv2 documents its Permissioned Resolver as deploying one proxy per name
owner with this same node-scoped, fine-grained approval model — see
ens/constants.py's address comment for how ENS_RESOLVER_ADDRESS picks
between a confirmed ENSv2 proxy and the PublicResolver fallback that is
known to expose this exact profile.
"""

from __future__ import annotations

from dataclasses import dataclass

from eth_account.signers.local import LocalAccount

from ens.abi import Function
from ens.constants import ENS_REGISTRY_ADDRESS
from ens.rpc import EthRpc, build_and_send

OWNER_FN = Function("owner", ("bytes32",), ("address",))
TEXT_FN = Function("text", ("bytes32", "string"), ("string",))
SET_TEXT_FN = Function("setText", ("bytes32", "string", "string"))
APPROVE_FN = Function("approve", ("bytes32", "address", "bool"))
IS_APPROVED_FOR_FN = Function("isApprovedFor", ("address", "bytes32", "address"), ("bool",))
IS_APPROVED_FOR_ALL_FN = Function("isApprovedForAll", ("address", "address"), ("bool",))


class ResolverPermissionError(PermissionError):
    """Raised when a signer isn't authorised to write a given node's records."""


@dataclass
class PermissionedResolver:
    """Thin wrapper around one deployed Permissioned Resolver contract.

    `rpc` is injected rather than constructed here so unit tests can pass a
    hand-written fake implementing EthRpc with no network access.
    scripts/register_agents_live.py is responsible for building the real
    SepoliaRpcClient for a live run.
    """

    rpc: EthRpc
    address: str
    registry_address: str = ENS_REGISTRY_ADDRESS

    def node_owner(self, node: bytes) -> str:
        """Who the ENS Registry says owns this node — the only address that
        can grant (or already implicitly holds) write access to it."""
        data = self.rpc.eth_call(self.registry_address, OWNER_FN.encode_call(node))
        (owner,) = OWNER_FN.decode_output(data)
        return owner

    def is_approved(self, node: bytes, address: str) -> bool:
        """Mirrors the resolver's on-chain `authorised(node)` check for one
        candidate address, without sending a transaction."""
        owner = self.node_owner(node)
        if owner.lower() == address.lower():
            return True
        data = self.rpc.eth_call(self.address, IS_APPROVED_FOR_ALL_FN.encode_call(owner, address))
        (approved_all,) = IS_APPROVED_FOR_ALL_FN.decode_output(data)
        if approved_all:
            return True
        data = self.rpc.eth_call(self.address, IS_APPROVED_FOR_FN.encode_call(owner, node, address))
        (approved,) = IS_APPROVED_FOR_FN.decode_output(data)
        return approved

    def grant_operator(self, node: bytes, delegate_address: str, *, signer: LocalAccount) -> str:
        """Grant `delegate_address` sole write access to one node's records.

        Only the node's registry owner can make this grant meaningfully —
        `approve()` records the approval under `msg.sender`'s own owner
        slot, so a non-owner calling it would grant an approval nobody's
        `isApprovedFor` lookup will ever match. Refuse client-side before
        wasting gas on a no-op transaction.
        """
        owner = self.node_owner(node)
        if signer.address.lower() != owner.lower():
            raise ResolverPermissionError(
                f"{signer.address} is not the registry owner of this node "
                f"({owner}); only the node owner can grant write access to it."
            )
        data = APPROVE_FN.encode_call(node, delegate_address, True)
        return build_and_send(self.rpc, self.address, data, signer)

    def set_text(self, node: bytes, key: str, value: str, *, signer: LocalAccount) -> str:
        """Write one ENSIP-26 text record. Refuses client-side if `signer`
        isn't authorised for `node` — see module docstring for why the real
        guarantee is the on-chain `authorised(node)` modifier, not this
        check alone."""
        if not self.is_approved(node, signer.address):
            raise ResolverPermissionError(
                f"{signer.address} is not authorised to write records for "
                "this node: it is neither the node's registry owner nor "
                "approved via approve(). Refusing before building a "
                "transaction the resolver contract would revert anyway."
            )
        data = SET_TEXT_FN.encode_call(node, key, value)
        return build_and_send(self.rpc, self.address, data, signer)

    def text(self, node: bytes, key: str) -> str:
        """Read one text record. No auth required — resolution is public."""
        data = self.rpc.eth_call(self.address, TEXT_FN.encode_call(node, key))
        (value,) = TEXT_FN.decode_output(data)
        return value
