"""ENSv2 PermissionedRegistry client -- the hierarchical registry that
replaces ENSv1's single flat ENSRegistry.

Verified against the real, currently-deployed
contracts/src/registry/PermissionedRegistry.sol (and its UUPS-upgradeable
UserRegistry variant, contracts/src/registry/UserRegistry.sol -- "designed
to be deployed as a proxy via VerifiableFactory for user-owned subdomain
registries") in ensdomains/contracts-v2, and against the *live* standard
ENSv2 Beta Sepolia deployment itself, not just the source: a read-only
`findOwner("agentria")` eth_call (selector 0x63560a8e, no ENS_PRIVATE_KEY
needed) against ENS_ETH_REGISTRY_ADDRESS returns a real, non-zero owner
(0x6907187b9e63abf8eb5a8f956aa556f20be95a5f), confirming `agentria.eth`
actually lives on this exact registry instance -- see
ens/constants.py's citation for the full verification, including why a
second "hackathon deployment" address set was ruled out.

Unlike ENSv1, ENS is not one flat contract. Names form a chain of
registries: the root .eth registry (ENS_ETH_REGISTRY_ADDRESS) holds
`agentria` as a single label whose entry points at agentria.eth's *own*
subregistry contract (a separate deployed instance) -- and RIA's four
subnames (`recon`/`oracle`/`exec`/`audit`) are labels registered *inside
that* subregistry, not inside the root .eth registry directly. A second
live, read-only call -- `getSubregistry("agentria")` against
ENS_ETH_REGISTRY_ADDRESS -- returned the zero address, confirming
agentria.eth does not have one yet, so register.py's job includes
deploying it (see ensure_subregistry() in register.py, using
ens/factory.py) before it can register any subnames into it. A third call
-- `getResolver("agentria")` -- returned a real, already-set resolver
address, but a *different* one from ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS
(its bytecode is a small ~1.3KB contract, nothing like PermissionedResolver's
~17.6KB, and contains none of its role-authorization selectors) -- i.e.
that's whatever generic resolver the ENS Sepolia app assigned
agentria.eth's own top-level name when the operator registered it, and is
unrelated to how RIA's four subnames get resolved. This is exactly why
this module resolves subregistries/resolvers dynamically via getSubregistry()/
getResolver() rather than ever hardcoding one.
"""

from __future__ import annotations

from dataclasses import dataclass

from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address

from ens.abi import Function
from ens.rpc import EthRpc, build_and_send

REGISTER_FN = Function(
    "register",
    ("string", "address", "address", "address", "uint256", "uint64"),
    ("uint256",),
)
GET_SUBREGISTRY_FN = Function("getSubregistry", ("string",), ("address",))
SET_SUBREGISTRY_FN = Function("setSubregistry", ("uint256", "address"))
GET_RESOLVER_FN = Function("getResolver", ("string",), ("address",))
GET_EXPIRY_FN = Function("getExpiry", ("uint256",), ("uint64",))
FIND_OWNER_FN = Function("findOwner", ("string",), ("address",))
ROLES_FN = Function("roles", ("uint256", "address"), ("uint256",))
# UserRegistry.initialize(rootAccount, roleBitmap) -- the `data` payload
# passed to VerifiableFactory.deployProxy() when deploying agentria.eth's
# subregistry (ens/factory.py delegatecalls this into the fresh proxy).
USER_REGISTRY_INITIALIZE_FN = Function("initialize", ("address", "uint256"))

ZERO_ADDRESS = "0x" + "00" * 20


@dataclass
class PermissionedRegistryClient:
    """Thin wrapper around one deployed PermissionedRegistry instance --
    could be the root .eth registry, or a subregistry deployed for one
    name owner (see ens/factory.py's deploy_proxy + UserRegistry)."""

    rpc: EthRpc
    address: str

    def find_owner(self, label: str) -> str:
        """IOwnedRegistry.findOwner(label) -- who currently owns `label`
        as a direct child of this registry instance, or the zero address
        if it's unregistered."""
        data = self.rpc.eth_call(self.address, FIND_OWNER_FN.encode_call(label))
        (owner,) = FIND_OWNER_FN.decode_output(data)
        return to_checksum_address(owner)

    def get_subregistry(self, label: str) -> str:
        data = self.rpc.eth_call(self.address, GET_SUBREGISTRY_FN.encode_call(label))
        (addr,) = GET_SUBREGISTRY_FN.decode_output(data)
        return to_checksum_address(addr)

    def get_resolver(self, label: str) -> str:
        data = self.rpc.eth_call(self.address, GET_RESOLVER_FN.encode_call(label))
        (addr,) = GET_RESOLVER_FN.decode_output(data)
        return to_checksum_address(addr)

    def get_expiry(self, label_id: int) -> int:
        data = self.rpc.eth_call(self.address, GET_EXPIRY_FN.encode_call(label_id))
        (expiry,) = GET_EXPIRY_FN.decode_output(data)
        return expiry

    def roles(self, resource: int, account: str) -> int:
        data = self.rpc.eth_call(self.address, ROLES_FN.encode_call(resource, account))
        (bitmap,) = ROLES_FN.decode_output(data)
        return bitmap

    def set_subregistry(self, label_id: int, subregistry_address: str, *, signer: LocalAccount) -> str:
        """setSubregistry(anyId, registry) -- requires `signer` to hold
        ROLE_SET_SUBREGISTRY on this label's resource (granted to
        whoever registered it, at registration time)."""
        data = SET_SUBREGISTRY_FN.encode_call(label_id, subregistry_address)
        return build_and_send(self.rpc, self.address, data, signer)

    def register(
        self,
        label: str,
        owner: str,
        subregistry_address: str,
        resolver_address: str,
        role_bitmap: int,
        expiry: int,
        *,
        signer: LocalAccount,
    ) -> str:
        """PermissionedRegistry.register(label, owner, registry, resolver,
        roleBitmap, expiry) -- creates one label as a child of this
        registry instance, owned by `owner`, resolved through
        `resolver_address`. Requires `signer` to hold ROLE_REGISTRAR at
        this registry's ROOT_RESOURCE."""
        data = REGISTER_FN.encode_call(
            label, owner, subregistry_address, resolver_address, role_bitmap, expiry
        )
        return build_and_send(self.rpc, self.address, data, signer)
