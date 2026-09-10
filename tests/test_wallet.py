"""Tests for hedera/wallet.py — no live credentials, no network.

Mocks the hiero_sdk_python SDK surface (Client, AccountId, PrivateKey,
CryptoGetAccountBalanceQuery) the same way test_subgraph_client.py mocks
httpx: substitute the names hedera.wallet imported, never touch the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hedera.wallet as wallet_module
from hedera.wallet import HederaWallet, WalletConfigError


class _FakeAccountId:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakeAccountId":
        if s == "bad-account":
            raise ValueError("bad account id")
        return cls(s)


class _FakePrivateKey:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakePrivateKey":
        if s == "bad-key":
            raise ValueError("bad private key")
        return cls(s)


def _patch_sdk(monkeypatch, fake_client: MagicMock | None = None):
    fake_client = fake_client or MagicMock(name="Client")
    monkeypatch.setattr(wallet_module, "AccountId", _FakeAccountId)
    monkeypatch.setattr(wallet_module, "PrivateKey", _FakePrivateKey)
    monkeypatch.setattr(
        wallet_module, "Client", MagicMock(for_testnet=MagicMock(return_value=fake_client))
    )
    return fake_client


def test_from_env_requires_account_id(monkeypatch):
    _patch_sdk(monkeypatch)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")
    with pytest.raises(WalletConfigError, match="HEDERA_ACCOUNT_ID"):
        HederaWallet.from_env()


def test_from_env_requires_private_key(monkeypatch):
    _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    with pytest.raises(WalletConfigError, match="HEDERA_PRIVATE_KEY"):
        HederaWallet.from_env()


def test_from_env_reports_both_missing(monkeypatch):
    _patch_sdk(monkeypatch)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    with pytest.raises(WalletConfigError, match="HEDERA_ACCOUNT_ID.*HEDERA_PRIVATE_KEY"):
        HederaWallet.from_env()


def test_from_env_builds_wallet_and_sets_operator(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    wallet = HederaWallet.from_env()

    assert wallet.account_id.raw == "0.0.1234"
    assert wallet.private_key.raw == "302e..."
    assert wallet.client is fake_client
    fake_client.set_operator.assert_called_once_with(wallet.account_id, wallet.private_key)


def test_from_env_rejects_malformed_account_id(monkeypatch):
    _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "bad-account")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")
    with pytest.raises(WalletConfigError, match="not a valid Hedera account id"):
        HederaWallet.from_env()


def test_from_env_rejects_malformed_private_key(monkeypatch):
    _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "bad-key")
    with pytest.raises(WalletConfigError, match="not a valid Hedera private key"):
        HederaWallet.from_env()


def test_get_balance_tinybars_delegates_to_query(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    fake_balance = MagicMock()
    fake_balance.hbars.to_tinybars.return_value = 500_000_000

    fake_query = MagicMock()
    fake_query.set_account_id.return_value = fake_query
    fake_query.execute.return_value = fake_balance
    fake_query_cls = MagicMock(return_value=fake_query)
    monkeypatch.setattr(wallet_module, "CryptoGetAccountBalanceQuery", fake_query_cls)

    wallet = HederaWallet.from_env()
    tinybars = wallet.get_balance_tinybars()

    assert tinybars == 500_000_000
    fake_query.set_account_id.assert_called_once_with(wallet.account_id)
    fake_query.execute.assert_called_once_with(fake_client)


def test_context_manager_closes_client(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    with HederaWallet.from_env() as wallet:
        assert wallet.client is fake_client
    fake_client.close.assert_called_once()
