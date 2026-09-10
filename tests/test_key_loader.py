"""Tests for hedera/key_loader.py — no live credentials, no network.

Direct unit coverage of `load_private_key` itself; hedera/wallet.py and
hedera/hcs_logger.py each have their own tests exercising this through
`from_env`, patched at the source here since both delegate to it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hedera.key_loader as key_loader_module
from hedera.key_loader import KeyLoadError, load_private_key

DEFAULT_PUBLIC_KEY_HEX = "aabbccddeeff"


class _FakePublicKey:
    def __init__(self, raw_hex: str):
        self._raw_hex = raw_hex

    def to_string_raw(self) -> str:
        return self._raw_hex


class _FakePrivateKey:
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


def _patch(monkeypatch, *, key_type: str = "ECDSA_SECP256K1", public_key_hex: str = DEFAULT_PUBLIC_KEY_HEX):
    monkeypatch.setattr(key_loader_module, "PrivateKey", _FakePrivateKey)
    _FakePrivateKey.public_key_hex = DEFAULT_PUBLIC_KEY_HEX
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"key": {"_type": key_type, "key": public_key_hex}}
    monkeypatch.setattr(key_loader_module.httpx, "get", MagicMock(return_value=fake_response))


def test_loads_ecdsa_account_with_ecdsa_loader(monkeypatch):
    _patch(monkeypatch, key_type="ECDSA_SECP256K1")
    key = load_private_key("0.0.1234", "raw-key")
    assert key.key_type == "ECDSA_SECP256K1"


def test_loads_ed25519_account_with_ed25519_loader(monkeypatch):
    _patch(monkeypatch, key_type="ED25519")
    key = load_private_key("0.0.1234", "raw-key")
    assert key.key_type == "ED25519"


def test_rejects_unrecognized_key_type(monkeypatch):
    _patch(monkeypatch, key_type="SOMETHING_ELSE")
    with pytest.raises(KeyLoadError, match="Unrecognized Hedera key type"):
        load_private_key("0.0.1234", "raw-key")


def test_rejects_key_not_matching_onchain_public_key(monkeypatch):
    _patch(monkeypatch, key_type="ECDSA_SECP256K1", public_key_hex="onchain-key")
    _FakePrivateKey.public_key_hex = "different-key"
    with pytest.raises(KeyLoadError, match="does not match"):
        load_private_key("0.0.1234", "raw-key")


def test_rejects_when_mirror_node_unreachable(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(key_loader_module.httpx, "get", _raise)
    with pytest.raises(KeyLoadError, match="mirror node"):
        load_private_key("0.0.1234", "raw-key")


def test_propagates_malformed_key_error(monkeypatch):
    _patch(monkeypatch, key_type="ECDSA_SECP256K1")
    with pytest.raises(ValueError, match="bad private key"):
        load_private_key("0.0.1234", "bad-key")
