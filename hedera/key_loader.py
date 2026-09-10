"""Shared Hedera private-key loading, disambiguated against the real
on-chain key algorithm of the account it belongs to.

Used by both `hedera/wallet.py` (ORACLE) and `hedera/hcs_logger.py`
(AUDIT) — extracted here rather than duplicated so the fix below can't
drift between the two.

`PrivateKey.from_string()` (hiero_sdk_python) is ambiguous for a raw
32-byte key: any 32 bytes is also a valid Ed25519 seed, so it silently
guesses Ed25519 first even for an ECDSA account -- which is what Hedera's
testnet portal issues by default, for EVM-address compatibility.
Confirmed against a real live run: this produced a key that signed with
the wrong algorithm entirely, cryptographically valid but for the wrong
public key, which surfaced downstream as
`invalid_exact_hedera_payload_signature_invalid` from the x402
facilitator with no indication the key type was the actual problem. So
`load_private_key` looks up the account's real key type and public key
from Hedera's public mirror node first, loads with the matching
`from_string_ecdsa`/`from_string_ed25519`, and verifies the derived
public key actually matches -- rather than guessing.
"""

from __future__ import annotations

import httpx
from hiero_sdk_python import PrivateKey

# Read-only, unauthenticated: Hedera's public mirror node, used only to look
# up which key algorithm (ED25519 vs ECDSA_secp256k1) an account was created
# with -- never to submit anything.
MIRROR_NODE_ACCOUNTS_URL = "https://testnet.mirrornode.hedera.com/api/v1/accounts"


class KeyLoadError(RuntimeError):
    """Raised when the account's key type can't be looked up, or the given
    private key doesn't match the account's real on-chain public key."""


def load_private_key(account_id_str: str, private_key_str: str) -> PrivateKey:
    """Load `private_key_str`, disambiguated against `account_id_str`'s real
    key algorithm on testnet. See module docstring for why this exists."""
    try:
        response = httpx.get(f"{MIRROR_NODE_ACCOUNTS_URL}/{account_id_str}", timeout=10.0)
        response.raise_for_status()
        key_info = response.json()["key"]
        key_type = key_info["_type"]
        onchain_public_key = key_info["key"].lower()
    except Exception as exc:
        raise KeyLoadError(
            f"Could not look up {account_id_str}'s key type from the Hedera testnet "
            f"mirror node (needed to load the private key with the right algorithm "
            f"-- ED25519 vs ECDSA -- rather than guessing wrong): {exc}"
        ) from exc

    if key_type == "ECDSA_SECP256K1":
        private_key = PrivateKey.from_string_ecdsa(private_key_str)
    elif key_type == "ED25519":
        private_key = PrivateKey.from_string_ed25519(private_key_str)
    else:
        raise KeyLoadError(f"Unrecognized Hedera key type for {account_id_str}: {key_type!r}")

    derived_public_key = private_key.public_key().to_string_raw().lower()
    if derived_public_key != onchain_public_key:
        raise KeyLoadError(
            f"Private key does not match the {key_type} public key on file "
            f"for {account_id_str} on testnet -- wrong key for this account id."
        )

    return private_key


__all__ = ["KeyLoadError", "load_private_key", "MIRROR_NODE_ACCOUNTS_URL"]
