"""ENS namehash (EIP-137) — pure, dependency-light, no network calls.

Every ENS name resolves to a `bytes32` "node" via this recursive algorithm.
It's the same 32-byte identifier the on-chain Registry and Resolver key all
of their per-name storage on, so register.py and resolver.py both go
through here rather than passing raw name strings around.
"""

from __future__ import annotations

from eth_utils import keccak

ZERO_NODE = b"\x00" * 32


def namehash(name: str) -> bytes:
    """Compute the ENS namehash of a dotted name, e.g. "ria-oracle.ria.eth".

    namehash("") == ZERO_NODE (the root node); every other name recurses
    through its labels right-to-left, matching EIP-137.
    """
    node = ZERO_NODE
    if name:
        for label in reversed(name.split(".")):
            node = keccak(node + labelhash(label))
    return node


def labelhash(label: str) -> bytes:
    """Hash of a single label (the part between dots), e.g. "ria-oracle"."""
    return keccak(text=label)
