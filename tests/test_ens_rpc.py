"""Tests for ens/rpc.py's receipt-waiting and in-flight-limit retry.

Regression coverage for a real failure during a live run: Infura rejected
a transaction broadcast with a policy error ("in-flight transaction limit
reached for delegated accounts") because the previous transaction from the
same signer hadn't been confirmed yet. build_and_send() now waits for each
transaction's receipt before returning (so at most one is ever in flight
per signer) and retries the send itself a few times if that error still
occurs.

Uses a minimal hand-rolled fake rather than tests/fake_chain.py's FakeChain
-- this is testing ens/rpc.py's own retry/wait control flow in isolation,
not ENS-specific contract behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from eth_account import Account

from ens.rpc import (
    RpcError,
    TransactionRevertedError,
    build_and_send,
    wait_for_receipt,
)

ADMIN_KEY = "0x" + "cc" * 32


@dataclass
class ScriptedRpc:
    """A fake EthRpc whose send_raw_transaction and get_transaction_receipt
    behaviour is scripted per-test via the lists below."""

    send_raises: list[Exception | None] = field(default_factory=lambda: [None])
    receipts: list[dict | None] = field(default_factory=lambda: [{"status": "0x1"}])
    send_calls: int = 0
    receipt_calls: int = 0

    def eth_call(self, to: str, data: bytes) -> bytes:
        raise NotImplementedError

    def get_transaction_count(self, address: str) -> int:
        return 0

    def gas_price(self) -> int:
        return 1_000_000_000

    def get_code(self, address: str) -> bytes:
        return b""

    def send_raw_transaction(self, raw: bytes) -> str:
        exc = self.send_raises[min(self.send_calls, len(self.send_raises) - 1)]
        self.send_calls += 1
        if exc is not None:
            raise exc
        return "0x" + "11" * 32

    def get_transaction_receipt(self, tx_hash: str) -> dict | None:
        receipt = self.receipts[min(self.receipt_calls, len(self.receipts) - 1)]
        self.receipt_calls += 1
        return receipt


def _signer():
    return Account.from_key(ADMIN_KEY)


def test_build_and_send_waits_for_receipt_before_returning(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    rpc = ScriptedRpc(receipts=[None, None, {"status": "0x1"}])

    tx_hash = build_and_send(rpc, "0x" + "22" * 20, b"", _signer())

    assert tx_hash == "0x" + "11" * 32
    assert rpc.receipt_calls == 3  # polled twice unconfirmed, then got the receipt


def test_wait_for_receipt_raises_on_reverted_status(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    rpc = ScriptedRpc(receipts=[{"status": "0x0"}])

    with pytest.raises(TransactionRevertedError):
        wait_for_receipt(rpc, "0x" + "11" * 32)


def test_wait_for_receipt_times_out_if_never_mined(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    rpc = ScriptedRpc(receipts=[None])
    times = iter([0.0, 0.0, 100.0])  # third monotonic() call looks past the deadline
    monkeypatch.setattr("ens.rpc.time.monotonic", lambda: next(times))

    with pytest.raises(TimeoutError):
        wait_for_receipt(rpc, "0x" + "11" * 32, timeout_s=10.0, poll_interval_s=0)


def test_build_and_send_retries_on_in_flight_limit_error(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    rpc = ScriptedRpc(
        send_raises=[
            RpcError("eth_sendRawTransaction failed: in-flight transaction limit reached for delegated accounts"),
            RpcError("eth_sendRawTransaction failed: in-flight transaction limit reached for delegated accounts"),
            None,
        ],
    )

    tx_hash = build_and_send(rpc, "0x" + "22" * 20, b"", _signer())

    assert tx_hash == "0x" + "11" * 32
    assert rpc.send_calls == 3


def test_build_and_send_does_not_retry_other_rpc_errors(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    rpc = ScriptedRpc(send_raises=[RpcError("eth_sendRawTransaction failed: nonce too low")])

    with pytest.raises(RpcError, match="nonce too low"):
        build_and_send(rpc, "0x" + "22" * 20, b"", _signer())

    assert rpc.send_calls == 1


def test_build_and_send_rebroadcasts_at_the_same_nonce_on_timeout(monkeypatch):
    """Regression test for a real stuck transaction: sent underpriced
    relative to where the network's gas price had since moved, it sat
    unconfirmed well past the receipt timeout. build_and_send() must not
    just give up -- it should resend at the same nonce with a bumped price
    (a standard replace-by-fee) rather than leaving the operator to
    manually unstick it."""
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    times = iter([0.0, 200.0, 300.0])  # attempt 1: deadline calc, timeout check; attempt 2: deadline calc
    monkeypatch.setattr("ens.rpc.time.monotonic", lambda: next(times))
    rpc = ScriptedRpc(
        send_raises=[None, None],
        receipts=[None, {"status": "0x1"}],  # attempt 1 never confirms; attempt 2 does immediately
    )

    tx_hash = build_and_send(rpc, "0x" + "22" * 20, b"", _signer())

    assert tx_hash == "0x" + "11" * 32
    assert rpc.send_calls == 2  # the original broadcast, then one rebroadcast


def test_build_and_send_gives_up_after_max_in_flight_limit_retries(monkeypatch):
    monkeypatch.setattr("ens.rpc.time.sleep", lambda *_: None)
    persistent_error = RpcError("eth_sendRawTransaction failed: in-flight transaction limit reached for delegated accounts")
    rpc = ScriptedRpc(send_raises=[persistent_error])  # every attempt fails the same way

    with pytest.raises(RpcError, match="in-flight transaction limit"):
        build_and_send(rpc, "0x" + "22" * 20, b"", _signer())

    assert rpc.send_calls == 5  # _IN_FLIGHT_LIMIT_RETRIES
