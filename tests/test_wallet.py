"""Tests for hedera/wallet.py — no live credentials, no network.

Mocks the hiero_sdk_python SDK surface (Client, AccountId, PrivateKey,
CryptoGetAccountBalanceQuery) the same way test_subgraph_client.py mocks
httpx: substitute the names hedera.wallet imported, never touch the network.
Also mocks the mirror-node key-type lookup `_load_private_key` added to
disambiguate ED25519 vs ECDSA private keys — see its docstring for the real
live-run bug (a "signature_invalid" 402 from the facilitator) this exists
to prevent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hedera.wallet as wallet_module
from hedera.wallet import HederaWallet, WalletConfigError

DEFAULT_PUBLIC_KEY_HEX = "aabbccddeeff"


class _FakeAccountId:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakeAccountId":
        if s == "bad-account":
            raise ValueError("bad account id")
        return cls(s)


class _FakePublicKey:
    def __init__(self, raw_hex: str):
        self._raw_hex = raw_hex

    def to_string_raw(self) -> str:
        return self._raw_hex


class _FakePrivateKey:
    # Overridable per test so a test can make the derived public key
    # mismatch the mirror node's, without touching every other test.
    public_key_hex = DEFAULT_PUBLIC_KEY_HEX

    def __init__(self, raw: str, key_type: str):
        self.raw = raw
        self.key_type = key_type

    @classmethod
    def from_string_ecdsa(cls, s: str) -> "_FakePrivateKey":
        if s == "bad-key":
            raise ValueError("bad private key")
        return cls(s, "ECDSA_SECP256K1")

    @classmethod
    def from_string_ed25519(cls, s: str) -> "_FakePrivateKey":
        if s == "bad-key":
            raise ValueError("bad private key")
        return cls(s, "ED25519")

    def public_key(self) -> _FakePublicKey:
        return _FakePublicKey(self.public_key_hex)


def _patch_sdk(monkeypatch, fake_client: MagicMock | None = None):
    fake_client = fake_client or MagicMock(name="Client")
    monkeypatch.setattr(wallet_module, "AccountId", _FakeAccountId)
    monkeypatch.setattr(wallet_module, "PrivateKey", _FakePrivateKey)
    monkeypatch.setattr(
        wallet_module, "Client", MagicMock(for_testnet=MagicMock(return_value=fake_client))
    )
    _FakePrivateKey.public_key_hex = DEFAULT_PUBLIC_KEY_HEX
    return fake_client


def _patch_mirror_node(monkeypatch, *, key_type: str = "ECDSA_SECP256K1", public_key_hex: str = DEFAULT_PUBLIC_KEY_HEX):
    """Mock the mirror-node GET this module makes to learn an account's real
    key algorithm + public key, without any network access."""
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"key": {"_type": key_type, "key": public_key_hex}}
    fake_get = MagicMock(return_value=fake_response)
    monkeypatch.setattr(wallet_module.httpx, "get", fake_get)
    return fake_get


def _patch_mirror_node_failure(monkeypatch, exc: Exception):
    def _raise(*args, **kwargs):
        raise exc

    monkeypatch.setattr(wallet_module.httpx, "get", _raise)


def test_from_env_requires_account_id(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")
    with pytest.raises(WalletConfigError, match="HEDERA_ACCOUNT_ID"):
        HederaWallet.from_env()


def test_from_env_requires_private_key(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    with pytest.raises(WalletConfigError, match="HEDERA_PRIVATE_KEY"):
        HederaWallet.from_env()


def test_from_env_reports_both_missing(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    with pytest.raises(WalletConfigError, match="HEDERA_ACCOUNT_ID.*HEDERA_PRIVATE_KEY"):
        HederaWallet.from_env()


def test_from_env_builds_wallet_and_sets_operator(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    wallet = HederaWallet.from_env()

    assert wallet.account_id.raw == "0.0.1234"
    assert wallet.private_key.raw == "302e..."
    assert wallet.client is fake_client
    fake_client.set_operator.assert_called_once_with(wallet.account_id, wallet.private_key)


def test_from_env_rejects_malformed_account_id(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "bad-account")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")
    with pytest.raises(WalletConfigError, match="not a valid Hedera account id"):
        HederaWallet.from_env()


def test_from_env_rejects_malformed_private_key(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "bad-key")
    with pytest.raises(WalletConfigError, match="not a valid Hedera private key"):
        HederaWallet.from_env()


def test_from_env_uses_ecdsa_loader_for_ecdsa_account(monkeypatch):
    """Regression test for the real live-run bug: an account whose on-chain
    key is ECDSA_secp256k1 (the default Hedera testnet portal issues, for
    EVM-address compatibility) must be loaded with `from_string_ecdsa`, not
    the ambiguous generic `from_string` that defaults to Ed25519 for any
    32-byte key and silently produces the wrong signing key."""
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch, key_type="ECDSA_SECP256K1")
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    wallet = HederaWallet.from_env()

    assert wallet.private_key.key_type == "ECDSA_SECP256K1"


def test_from_env_uses_ed25519_loader_for_ed25519_account(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch, key_type="ED25519")
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    wallet = HederaWallet.from_env()

    assert wallet.private_key.key_type == "ED25519"


def test_from_env_rejects_key_not_matching_account(monkeypatch):
    """The other half of the regression coverage: even loaded with the
    right algorithm, a private key that doesn't derive the account's real
    on-chain public key must fail loudly here, not downstream as a cryptic
    facilitator-side signature rejection."""
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch, key_type="ECDSA_SECP256K1", public_key_hex="onchain-pub-key")
    _FakePrivateKey.public_key_hex = "different-derived-pub-key"
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    with pytest.raises(WalletConfigError, match="does not match"):
        HederaWallet.from_env()


def test_from_env_rejects_when_mirror_node_lookup_fails(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node_failure(monkeypatch, RuntimeError("connection refused"))
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    with pytest.raises(WalletConfigError, match="mirror node"):
        HederaWallet.from_env()


def test_get_balance_tinybars_delegates_to_query(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
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
    _patch_mirror_node(monkeypatch)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    monkeypatch.setenv("HEDERA_PRIVATE_KEY", "302e...")

    with HederaWallet.from_env() as wallet:
        assert wallet.client is fake_client
    fake_client.close.assert_called_once()
