"""Permissioned Resolver interactions — RIA's real per-agent write isolation.

This is the piece the ENS bonus track is actually judged on: EXEC's key
must not be able to overwrite ORACLE's ENS text records, and that has to
be enforced *by the resolver contract itself*, not just by RIA's own code
being polite about which `agent_id` string it passes around.

The mechanism is Enhanced Access Control (EAC), not ENSv1's
approve()/isApprovedFor()/isApprovedForAll() (an earlier version of this
file used that model as a documented ENSv1-shaped fallback while ENSv2
addresses weren't confirmed -- they're confirmed now, and the real
mechanism is different, so this file was rewritten rather than patched).
Verified against the real, currently-deployed
contracts/src/resolver/PermissionedResolver.sol in ensdomains/contracts-v2
(fetched directly from GitHub), and cross-checked against the actual
deployed bytecode at ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS on Sepolia:
its runtime code contains the real 4-byte selectors for setText, text,
authorizeNameRoles, authorizeTextRoles, authorizeDataRoles,
authorizeAddrRoles and grantRootRoles (checked via eth_getCode against a
public RPC, no ENS_PRIVATE_KEY needed) -- i.e. this isn't just "the docs
say this", the contract actually deployed at that address really does
expose these functions.

Every (node, record-type) pair is its own EAC "resource":
`resource(node, part) = keccak256(node, part)` (PermissionedResolverLib.resource,
`part = 0` meaning "any record type"). A write like
`setText(node, key, value)` is gated by
`onlyPartRoles(node, partHash(key), ROLE_SET_TEXT)`, which passes only if
the caller holds ROLE_SET_TEXT on resource(node, partHash(key)),
resource(0, partHash(key)) (a global grant for that one key across every
name), or resource(node, 0) (a global grant for every record on that one
name) -- see PermissionedResolver.sol's own "Setters with node check"
table in its module docstring. Critically, this scoping is *per node*:
granting EXEC's derived address ROLE_SET_TEXT on exec.agentria.eth's
resource(node, 0) never touches oracle.agentria.eth's resource -- that's a
completely different keccak256 input. register.py (as the resolver
proxy's ROOT_RESOURCE admin) grants exactly one address -- that agent's
own derived address -- ROLE_SET_TEXT scoped to that agent's own node via
authorize_agent()/authorizeNameRoles(), and never touches any other
node's resource. If EXEC's derived key calls setText(oracle_node, ...),
none of the three resource checks above can match, and
PermissionedResolver's onlyPartRoles modifier reverts with
EACUnauthorizedAccountRoles -- real, on-chain enforcement, independent of
anything in this file.

(One shared resolver *instance* serves all four subnames -- ENSv2's EAC
scoping is already per-node, so four separate resolver proxies aren't
needed for isolation; an earlier draft of this rewrite considered that,
sourced from an ETHOnline-2026-hackathon-specific preview docs site
claiming resolver-wide-only roles, but that site's claimed deployment
addresses don't match where agentria.eth actually lives on-chain -- see
ens/constants.py's citation -- and its claimed role/function names
(`grantSetterRoles` etc.) are absent from the bytecode actually deployed
at the address this module uses. Rejected in favour of the primary
source + on-chain bytecode evidence above.)

The client-side check in `is_authorized_for_node()` below is *defense in
depth*: it mirrors the exact same bitmap math (ens/eac.py, shared with
tests/fake_chain.py's server-side enforcement) so a bad write fails fast
in Python instead of spending gas on a transaction that would revert
anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

from eth_account.signers.local import LocalAccount
from eth_utils import keccak

from ens.abi import Function
from ens.constants import RESOLVER_ADMIN_ROLE_BITMAP, ROLE_SET_TEXT
from ens.dns_name import dns_encode
from ens.eac import ROOT_RESOURCE, has_roles
from ens.factory import deploy_proxy
from ens.rpc import EthRpc, build_and_send

SET_TEXT_FN = Function("setText", ("bytes32", "string", "string"))
TEXT_FN = Function("text", ("bytes32", "string"), ("string",))
AUTHORIZE_NAME_ROLES_FN = Function(
    "authorizeNameRoles", ("bytes", "uint256", "address", "bool"), ("bool",)
)
ROLES_FN = Function("roles", ("uint256", "address"), ("uint256",))
# PermissionedResolver.initialize(admin, roleBitmap, setters) -- the
# `data` payload passed to VerifiableFactory.deployProxy() when deploying
# RIA's shared resolver proxy (ens/factory.py delegatecalls this into the
# fresh proxy). `setters` (bytes[]) lets a caller multicall additional
# writes during init; RIA doesn't need any, so it's always [].
INITIALIZE_FN = Function("initialize", ("address", "uint256", "bytes[]"))

ZERO_NODE = b"\x00" * 32


class ResolverPermissionError(PermissionError):
    """Raised when a signer isn't authorised to write a given node's records."""


def resource(node: bytes, part: bytes = ZERO_NODE) -> int:
    """PermissionedResolverLib.resource(node, part): keccak256(node, part)
    as a uint256 EAC resource id, or 0 (ROOT_RESOURCE) if both are zero."""
    if node == ZERO_NODE and part == ZERO_NODE:
        return ROOT_RESOURCE
    return int.from_bytes(keccak(node + part), "big")


def text_part(key: str) -> bytes:
    """PermissionedResolverLib.partHash(string): keccak256(bytes(key))."""
    return keccak(text=key)


@dataclass
class PermissionedResolver:
    """Thin wrapper around one deployed PermissionedResolver proxy.

    `rpc` is injected rather than constructed here so unit tests can pass
    a hand-written fake implementing EthRpc with no network access.
    scripts/register_agents_live.py is responsible for building the real
    SepoliaRpcClient for a live run.
    """

    rpc: EthRpc
    address: str

    def roles(self, node: bytes, account: str) -> int:
        """Raw EnhancedAccessControl.roles(resource(node,0), account) --
        the roles `account` holds *directly* on the "any record on this
        one name" resource authorize_agent() grants into. Does not
        include ROOT_RESOURCE roles; see root_roles()/is_authorized_for_node()."""
        data = self.rpc.eth_call(self.address, ROLES_FN.encode_call(resource(node), account))
        (bitmap,) = ROLES_FN.decode_output(data)
        return bitmap

    def root_roles(self, account: str) -> int:
        """Raw EnhancedAccessControl.roles(ROOT_RESOURCE, account) on this
        resolver instance -- roles here apply to every node (see
        ens/eac.py's effective_roles)."""
        data = self.rpc.eth_call(self.address, ROLES_FN.encode_call(ROOT_RESOURCE, account))
        (bitmap,) = ROLES_FN.decode_output(data)
        return bitmap

    def is_authorized_for_node(self, node: bytes, account: str) -> bool:
        """Mirrors PermissionedResolver.onlyPartRoles's node-wide branch
        (resource(node, 0)) for ROLE_SET_TEXT -- the exact grant shape
        register.py always uses (see authorize_agent()). Reads both the
        node-scoped and ROOT_RESOURCE roles and applies the same
        effective-roles OR-in the real contract does (ens/eac.has_roles),
        so it can only say "authorised" when the contract itself would."""
        roles = {
            (ROOT_RESOURCE, account.lower()): self.root_roles(account),
            (resource(node), account.lower()): self.roles(node, account),
        }
        return has_roles(roles, resource(node), ROLE_SET_TEXT, account)

    def authorize_agent(self, name: str, agent_address: str, *, signer: LocalAccount) -> str:
        """authorizeNameRoles(dns_encode(name), ROLE_SET_TEXT,
        agent_address, true) -- grants `agent_address` ROLE_SET_TEXT on
        resource(namehash(name), 0), i.e. every text record on `name` and
        nothing else. Requires `signer` to hold ROLE_SET_TEXT_ADMIN
        (directly, or via ROOT_RESOURCE) -- the resolver proxy's deployer
        gets that at initialize() time, see deploy_resolver_proxy()."""
        data = AUTHORIZE_NAME_ROLES_FN.encode_call(
            dns_encode(name), ROLE_SET_TEXT, agent_address, True
        )
        return build_and_send(self.rpc, self.address, data, signer)

    def set_text(self, node: bytes, key: str, value: str, *, signer: LocalAccount) -> str:
        """Write one ENSIP-26 text record. Refuses client-side if `signer`
        isn't authorised for `node` — see module docstring for why the
        real guarantee is PermissionedResolver's on-chain
        `onlyPartRoles`/EACUnauthorizedAccountRoles check, not this check
        alone."""
        if not self.is_authorized_for_node(node, signer.address):
            raise ResolverPermissionError(
                f"{signer.address} does not hold ROLE_SET_TEXT on this "
                "node's EAC resource (directly or via ROOT_RESOURCE): "
                "refusing before building a transaction "
                "PermissionedResolver's onlyPartRoles modifier would "
                "revert anyway (EACUnauthorizedAccountRoles)."
            )
        data = SET_TEXT_FN.encode_call(node, key, value)
        return build_and_send(self.rpc, self.address, data, signer)

    def text(self, node: bytes, key: str) -> str:
        """Read one text record. No auth required — resolution is public."""
        data = self.rpc.eth_call(self.address, TEXT_FN.encode_call(node, key))
        (value,) = TEXT_FN.decode_output(data)
        return value


def deploy_resolver_proxy(
    rpc: EthRpc,
    *,
    factory_address: str,
    implementation_address: str,
    admin: LocalAccount,
    salt: int,
) -> PermissionedResolver:
    """Deploy (once) and initialize one PermissionedResolver proxy shared
    by RIA's four subnames, via ENSv2's VerifiableFactory (ens/factory.py).

    `admin` receives RESOLVER_ADMIN_ROLE_BITMAP (ROLE_SET_TEXT_ADMIN |
    ROLE_UPGRADE_ADMIN) at the proxy's ROOT_RESOURCE -- enough to call
    authorize_agent() per node, deliberately never enough to call
    setText() itself (it never holds the plain ROLE_SET_TEXT bit — see
    ens/eac.py's admin-vs-regular-bit note and
    ens/constants.py's RESOLVER_ADMIN_ROLE_BITMAP)."""
    init_data = INITIALIZE_FN.encode_call(admin.address, RESOLVER_ADMIN_ROLE_BITMAP, [])
    address = deploy_proxy(
        rpc, factory_address, implementation_address, salt, init_data, signer=admin
    )
    return PermissionedResolver(rpc=rpc, address=address)
