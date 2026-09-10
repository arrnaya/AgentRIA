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

from hiero_sdk_python import (
    AccountId,
    Client,
    CryptoGetAccountBalanceQuery,
    Hbar,
    PrivateKey,
)

from hedera.key_loader import KeyLoadError, load_private_key


class WalletConfigError(RuntimeError):
    """Raised when required Hedera credentials are missing or malformed."""


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
            private_key = load_private_key(account_id_str, private_key_str)
        except KeyLoadError as exc:
            raise WalletConfigError(str(exc)) from exc
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
