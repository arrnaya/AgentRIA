"""Tests for hedera/hcs_logger.py — no live credentials, no network.

Mocks the hiero_sdk_python SDK surface the same way test_wallet.py does:
substitute the names hedera.hcs_logger imported, never touch the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import hedera.hcs_logger as hcs_module
from hedera.hcs_logger import HcsConfigError, HcsLogger, HcsSubmitError


class _FakeAccountId:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakeAccountId":
        return cls(s)

    def __str__(self) -> str:
        return self.raw


class _FakePrivateKey:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakePrivateKey":
        return cls(s)


class _FakeTopicId:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakeTopicId":
        return cls(s)

    def __str__(self) -> str:
        return self.raw


def _patch_sdk(monkeypatch, fake_client: MagicMock | None = None):
    fake_client = fake_client or MagicMock(name="Client")
    monkeypatch.setattr(hcs_module, "AccountId", _FakeAccountId)
    monkeypatch.setattr(hcs_module, "PrivateKey", _FakePrivateKey)
    monkeypatch.setattr(hcs_module, "TopicId", _FakeTopicId)
    monkeypatch.setattr(hcs_module, "Client", MagicMock(for_testnet=MagicMock(return_value=fake_client)))
    return fake_client


def _env(monkeypatch, **overrides):
    defaults = {
        "HEDERA_ACCOUNT_ID": "0.0.1234",
        "HEDERA_PRIVATE_KEY": "302e...",
        "HCS_TOPIC_ID": "0.0.7777",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_from_env_requires_all_three(monkeypatch):
    _patch_sdk(monkeypatch)
    _env(monkeypatch, HCS_TOPIC_ID=None)
    with pytest.raises(HcsConfigError, match="HCS_TOPIC_ID"):
        HcsLogger.from_env()


def test_from_env_builds_logger_and_sets_operator(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    _env(monkeypatch)

    logger = HcsLogger.from_env()

    assert logger.topic_id.raw == "0.0.7777"
    fake_client.set_operator.assert_called_once_with(logger.account_id, logger.private_key)


def test_create_topic_returns_topic_id_string():
    fake_client = MagicMock()
    fake_receipt = MagicMock()
    fake_receipt.topic_id = _FakeTopicId("0.0.9999")

    fake_tx = MagicMock()
    fake_tx.freeze_with.return_value = fake_tx
    fake_tx.sign.return_value = fake_tx
    fake_tx.execute.return_value = fake_receipt

    fake_tx_cls = MagicMock(return_value=fake_tx)
    fake_tx.set_memo = MagicMock(return_value=fake_tx)

    import hedera.hcs_logger as mod

    original = mod.TopicCreateTransaction
    mod.TopicCreateTransaction = fake_tx_cls
    try:
        topic_id = HcsLogger.create_topic(
            account_id=_FakeAccountId("0.0.1234"),
            private_key=_FakePrivateKey("key"),
            client=fake_client,
        )
    finally:
        mod.TopicCreateTransaction = original

    assert topic_id == "0.0.9999"
    fake_tx.freeze_with.assert_called_once_with(fake_client)


def test_create_topic_raises_when_receipt_has_no_topic_id():
    fake_client = MagicMock()
    fake_receipt = MagicMock()
    fake_receipt.topic_id = None

    fake_tx = MagicMock()
    fake_tx.set_memo.return_value = fake_tx
    fake_tx.freeze_with.return_value = fake_tx
    fake_tx.sign.return_value = fake_tx
    fake_tx.execute.return_value = fake_receipt

    import hedera.hcs_logger as mod

    original = mod.TopicCreateTransaction
    mod.TopicCreateTransaction = MagicMock(return_value=fake_tx)
    try:
        with pytest.raises(HcsSubmitError, match="no topic_id"):
            HcsLogger.create_topic(
                account_id=_FakeAccountId("0.0.1234"), private_key=_FakePrivateKey("key"), client=fake_client
            )
    finally:
        mod.TopicCreateTransaction = original


def _build_logger_with_fake_submit(monkeypatch, sequence_number=42):
    _patch_sdk(monkeypatch)
    _env(monkeypatch)
    logger = HcsLogger.from_env()

    fake_receipt = MagicMock()
    fake_receipt.transaction_id = "0.0.1234@1700000000.000000000"
    fake_receipt.topic_sequence_number = sequence_number

    fake_tx = MagicMock()
    fake_tx.set_topic_id.return_value = fake_tx
    fake_tx.set_message.return_value = fake_tx
    fake_tx.freeze_with.return_value = fake_tx
    fake_tx.sign.return_value = fake_tx
    fake_tx.execute.return_value = fake_receipt

    monkeypatch.setattr(hcs_module, "TopicMessageSubmitTransaction", MagicMock(return_value=fake_tx))
    return logger, fake_tx, fake_receipt


def test_log_payment_submits_and_returns_receipt_info(monkeypatch):
    logger, fake_tx, _ = _build_logger_with_fake_submit(monkeypatch)

    result = logger.log_payment(
        tool_name="get_risk_score", hbar_amount=0.002, hedera_tx_id="0.0.5555@1700000000.000000000"
    )

    assert result["topic_id"] == "0.0.7777"
    assert result["consensus_tx_id"] == "0.0.1234@1700000000.000000000"
    assert result["topic_sequence_number"] == 42
    assert "content_hash" in result

    # The submitted message is the event plus a content_hash, JSON-encoded.
    fake_tx.set_message.assert_called_once()
    (submitted_bytes,), _kwargs = fake_tx.set_message.call_args
    import json

    submitted = json.loads(submitted_bytes)
    assert submitted["type"] == "PAYMENT"
    assert submitted["tool_name"] == "get_risk_score"
    assert submitted["hbar_amount"] == 0.002
    assert "content_hash" in submitted


def test_log_event_hash_is_deterministic_for_same_content(monkeypatch):
    logger, _, _ = _build_logger_with_fake_submit(monkeypatch)
    hash1 = logger._content_hash({"a": 1, "b": 2})
    hash2 = logger._content_hash({"b": 2, "a": 1})  # key order shouldn't matter
    assert hash1 == hash2


def test_log_event_raises_hcs_submit_error_on_execute_failure(monkeypatch):
    logger, fake_tx, _ = _build_logger_with_fake_submit(monkeypatch)
    fake_tx.execute.side_effect = RuntimeError("network down")

    with pytest.raises(HcsSubmitError, match="Failed to submit HCS message"):
        logger.log_event({"type": "AUDIT"})
