"""Pure bitmap math for ENSv2's Enhanced Access Control (EAC) roles.

Shared by ens/resolver.py (client-side pre-check), ens/registry.py, and
tests/fake_chain.py (server-side enforcement) so both sides implement the
*same* rule rather than two independently-drifting approximations of it --
the same discipline the old ENSv1-era resolver.py used for
approve()/isApprovedFor(), carried over to the real ENSv2 mechanism.

Verified against the real, currently-deployed
contracts/src/access-control/EnhancedAccessControl.sol and
contracts/src/access-control/libraries/EACBaseRolesLib.sol in
ensdomains/contracts-v2 (fetched directly from GitHub; see
ens/constants.py for how that maps onto the live Sepolia deployment
agentria.eth actually lives on).

Bitmap layout (uint256): 32 "regular" roles in the low 128 bits (one
nybble each), each with a matching "admin" role at the same nybble
position in the high 128 bits (admin_bit = regular_bit << 128). Holding a
role's admin bit lets you grant/revoke that role (and its own admin bit)
on a resource; it does NOT by itself let you exercise the *regular*
permission -- callers must hold the regular bit directly for that
(EnhancedAccessControl.hasRoles / PermissionedResolver.onlyPartRoles both
check the literal bitmap, not "settable" roles).

Roles granted at ROOT_RESOURCE (0) apply to every resource on that same
contract instance -- EnhancedAccessControl._effectiveRoles ORs a caller's
ROOT_RESOURCE roles into whatever it holds on the specific resource being
checked. That's why register.py's admin wallet, holding
ROLE_SET_TEXT_ADMIN at a resolver proxy's ROOT_RESOURCE, can grant
ROLE_SET_TEXT on any individual node's resource -- and why an agent's
derived key, holding nothing at ROOT_RESOURCE and nothing on any node but
its own, can never satisfy the check for another agent's node.
"""

from __future__ import annotations

ROOT_RESOURCE = 0
ADMIN_SHIFT = 128


def admin_bit(regular_bit: int) -> int:
    """The admin-role bit corresponding to one regular-role bit."""
    return regular_bit << ADMIN_SHIFT


def with_admin_roles_applied(role_bitmap: int) -> int:
    """EACBaseRolesLib.withAdminRolesApplied: keep only the admin-role
    bits of `role_bitmap`, and mirror each one down into its matching
    regular-role bit. This turns "roles effectively held" into "roles
    that can be granted to someone else" -- holding an admin bit is what
    makes both the regular role and the admin role itself grantable."""
    admin_only = role_bitmap >> ADMIN_SHIFT
    return (admin_only << ADMIN_SHIFT) | admin_only


def effective_roles(roles: dict[tuple[int, str], int], resource: int, account: str) -> int:
    """EnhancedAccessControl._effectiveRoles: ROOT_RESOURCE roles apply to
    every resource, OR'd in with whatever's granted on `resource` itself.
    `roles` is a plain {(resource, lowercased_account): bitmap} dict, the
    same shape both PermissionedRegistryClient/PermissionedResolver's
    client-side checks and tests/fake_chain.py's server-side state use."""
    account = account.lower()
    return roles.get((ROOT_RESOURCE, account), 0) | roles.get((resource, account), 0)


def has_roles(roles: dict[tuple[int, str], int], resource: int, role_bitmap: int, account: str) -> bool:
    """EnhancedAccessControl.hasRoles: does `account` hold every bit in
    `role_bitmap`, on `resource` or via ROOT_RESOURCE?"""
    return effective_roles(roles, resource, account) & role_bitmap == role_bitmap


def settable_roles(roles: dict[tuple[int, str], int], resource: int, account: str) -> int:
    """EnhancedAccessControl._getSettableRoles (base, non-token-scoped
    form used by PermissionedResolver): the roles `account` is allowed to
    grant to someone else on `resource`, derived from whichever *admin*
    bits it effectively holds there."""
    return with_admin_roles_applied(effective_roles(roles, resource, account))


def can_grant_roles(roles: dict[tuple[int, str], int], resource: int, role_bitmap: int, account: str) -> bool:
    """EnhancedAccessControl._checkCanGrantRoles, as a boolean: can
    `account` grant every bit in `role_bitmap` on `resource`?"""
    return (role_bitmap & ~settable_roles(roles, resource, account)) == 0
