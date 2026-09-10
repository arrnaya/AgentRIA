"""DNS wire-format name encoding (ENSIP-10 style).

ENSv2's PermissionedResolver.authorizeNameRoles() (and its
authorizeTextRoles/authorizeDataRoles/authorizeAddrRoles siblings) take a
name as `bytes calldata toName` -- the DNS wire encoding
`NameCoder.namehash()` decodes on-chain -- not a dotted string and not a
bare bytes32 node. Verified against the real, currently-deployed
contracts/src/resolver/PermissionedResolver.sol in ensdomains/contracts-v2:

    function authorizeNameRoles(bytes calldata toName, uint256 roleBitmap,
        address account, bool grant) external returns (bool)

ens/namehash.py's namehash() still produces the identical bytes32 node for
the equivalent dotted name -- that's an EIP-137/ENSIP-10 invariant, and
it's what setText()/text() take directly (those weren't affected by the
ENSv2 rewrite). This module only covers encoding the *name itself* for the
handful of calls that need it.
"""

from __future__ import annotations


def dns_encode(name: str) -> bytes:
    """Encode a dotted name ("recon.agentria.eth") as DNS wire format:
    each label prefixed by its one-byte length, terminated by a zero
    byte. The empty name ("", the root) encodes to a single zero byte."""
    if not name:
        return b"\x00"
    out = bytearray()
    for label in name.split("."):
        label_bytes = label.encode("utf-8")
        if not label_bytes or len(label_bytes) > 63:
            raise ValueError(f"invalid DNS label {label!r} in {name!r}")
        out.append(len(label_bytes))
        out.extend(label_bytes)
    out.append(0)
    return bytes(out)
