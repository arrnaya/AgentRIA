"""Thin `hiero_sdk_python` wrapper for ORACLE's funded Hedera testnet account.

Containment rule: this module — and `hedera/x402_client.py` built on top of
it — is the ONLY code in this repo allowed to hold wallet credentials or
sign a transaction. No other agent module (`recon.py`, `scout.py`,
`risk.py`, `exec.py`, `audit.py`) may import `HederaWallet`.

Every construction path here works entirely on `os.environ` — the wallet
never opens a `.env` file itself; whatever process launches it (a script,
a test, `python-dotenv` upstream) is responsible for populating the
environment first, exactly like `graph.subgraph_client.SubgraphClient`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from hiero_sdk_python import (
    AccountId,
    Client,
    CryptoGetAccountBalanceQuery,
    Hbar,
    PrivateKey,
)

# Read-only, unauthenticated: Hedera's public mirror node, used only to look
# up which key algorithm (ED25519 vs ECDSA_secp256k1) an account was created
# with -- never to submit anything.
MIRROR_NODE_ACCOUNTS_URL = "https://testnet.mirrornode.hedera.com/api/v1/accounts"


class WalletConfigError(RuntimeError):
    """Raised when required Hedera credentials are missing or malformed."""


def _load_private_key(account_id_str: str, private_key_str: str) -> PrivateKey:
    """Load `private_key_str`, disambiguated against the real key algorithm
    of `account_id_str` on testnet.

    `PrivateKey.from_string()` is ambiguous for a 32-byte raw key: any 32
    bytes is also a valid Ed25519 seed, so it silently guesses Ed25519 first
    even for an ECDSA account (which is what Hedera's testnet portal issues
    by default, for EVM-address compatibility) -- producing a key that
    signs with the wrong algorithm entirely. Every signature it makes is
    then valid cryptographically but for the wrong public key, which the
    facilitator's own signature check rejects as
    invalid_exact_hedera_payload_signature_invalid with no indication the
    key type was the actual problem. So this looks up the account's real
    key type and public key from the mirror node first and loads + verifies
    against that, rather than guessing.
    """
    try:
        response = httpx.get(f"{MIRROR_NODE_ACCOUNTS_URL}/{account_id_str}", timeout=10.0)
        response.raise_for_status()
        key_info = response.json()["key"]
        key_type = key_info["_type"]
        onchain_public_key = key_info["key"].lower()
    except Exception as exc:
        raise WalletConfigError(
            f"Could not look up {account_id_str}'s key type from the Hedera testnet "
            f"mirror node (needed to load HEDERA_PRIVATE_KEY with the right "
            f"algorithm -- ED25519 vs ECDSA -- rather than guessing wrong): {exc}"
        ) from exc

    if key_type == "ECDSA_SECP256K1":
        private_key = PrivateKey.from_string_ecdsa(private_key_str)
    elif key_type == "ED25519":
        private_key = PrivateKey.from_string_ed25519(private_key_str)
    else:
        raise WalletConfigError(f"Unrecognized Hedera key type for {account_id_str}: {key_type!r}")

    derived_public_key = private_key.public_key().to_string_raw().lower()
    if derived_public_key != onchain_public_key:
        raise WalletConfigError(
            f"HEDERA_PRIVATE_KEY does not match the {key_type} public key on file "
            f"for {account_id_str} on testnet -- wrong key for this account id."
        )

    return private_key


@dataclass
class HederaWallet:
    """Operator wallet + a Hedera testnet `Client` bound to it.

    `Client` in `hiero_sdk_python` holds live network/channel state, so this
    wraps it rather than re-deriving account/key on every call — construct
    once per process (or per test) and reuse.
    """

    account_id: AccountId
    private_key: PrivateKey
    client: Client

    @classmethod
    def from_env(cls) -> "HederaWallet":
        """Build a wallet from `HEDERA_ACCOUNT_ID` / `HEDERA_PRIVATE_KEY`.

        Raises `WalletConfigError` immediately if either is unset — ORACLE
        has no fallback payment path, so failing loud here beats a
        confusing downstream 402 retry loop. Never logs or echoes the key.
        """
        account_id_str = os.environ.get("HEDERA_ACCOUNT_ID")
        private_key_str = os.environ.get("HEDERA_PRIVATE_KEY")

        missing = [
            name
            for name, value in (
                ("HEDERA_ACCOUNT_ID", account_id_str),
                ("HEDERA_PRIVATE_KEY", private_key_str),
            )
            if not value
        ]
        if missing:
            raise WalletConfigError(
                "Missing required env var(s): "
                + ", ".join(missing)
                + ". Get a free funded testnet account from the Hedera "
                "Testnet Portal — see README.md > Environment Variables."
            )

        try:
            account_id = AccountId.from_string(account_id_str)
        except Exception as exc:  # pragma: no cover - defensive, SDK-specific
            raise WalletConfigError(
                f"HEDERA_ACCOUNT_ID is not a valid Hedera account id: {exc}"
            ) from exc

        try:
            private_key = _load_private_key(account_id_str, private_key_str)
        except WalletConfigError:
            raise
        except Exception as exc:  # pragma: no cover - defensive, SDK-specific
            raise WalletConfigError(
                f"HEDERA_PRIVATE_KEY is not a valid Hedera private key: {exc}"
            ) from exc

        client = Client.for_testnet()
        client.set_operator(account_id, private_key)
        return cls(account_id=account_id, private_key=private_key, client=client)

    def get_balance_tinybars(self) -> int:
        """Query the operator account's live HBAR balance, in tinybars."""
        balance = (
            CryptoGetAccountBalanceQuery()
            .set_account_id(self.account_id)
            .execute(self.client)
        )
        return balance.hbars.to_tinybars()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "HederaWallet":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["HederaWallet", "WalletConfigError"]
