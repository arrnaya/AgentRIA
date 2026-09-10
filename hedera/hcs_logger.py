"""AUDIT's Hedera Consensus Service (HCS) writer — the tamper-proof audit trail.

Per README.md > "x402 Payment Flow — Step by Step" (step 8) and > "Layer 3
— Identity & Visibility": AUDIT writes a JSON payload — tool name, HBAR
amount, Hedera tx ID, response hash — to an HCS topic after every payment
and EXEC cycle, and the dashboard's "HCS Audit Trail" panel reads it back.

Not a payment-authority module: submitting an HCS message costs a small,
fixed Hedera network fee — the cost of writing to the ledger, not the
commercial x402 payment ORACLE makes to Blocky402
(`hedera/x402_client.py`). The two are conceptually distinct even though,
per README's Environment Variables table (only one funded testnet account
defined for the whole project today), they currently run against the same
operator account. This module intentionally does not import
`hedera.wallet.HederaWallet` — that class's docstring reserves it for
ORACLE — and builds its own minimal operator/client pair instead, so the
containment boundary stays legible in the code, not just in prose.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from hiero_sdk_python import (
    AccountId,
    Client,
    PrivateKey,
    TopicCreateTransaction,
    TopicId,
    TopicMessageSubmitTransaction,
)

logger = logging.getLogger("ria.hcs_logger")


class HcsConfigError(RuntimeError):
    """Raised when required Hedera credentials or the topic id are missing."""


class HcsSubmitError(RuntimeError):
    """Raised when submitting a message to the HCS topic fails."""


@dataclass
class HcsLogger:
    """Writes AUDIT's JSON payloads to one Hedera Consensus Service topic."""

    account_id: AccountId
    private_key: PrivateKey
    client: Client
    topic_id: TopicId

    @classmethod
    def from_env(cls) -> "HcsLogger":
        """Build from `HEDERA_ACCOUNT_ID` / `HEDERA_PRIVATE_KEY` / `HCS_TOPIC_ID`.

        `HCS_TOPIC_ID` is not created automatically — run `create_topic()`
        once (a standalone, human-triggered step, same discipline as any
        other on-chain transaction) and set the resulting id.
        """
        account_id_str = os.environ.get("HEDERA_ACCOUNT_ID")
        private_key_str = os.environ.get("HEDERA_PRIVATE_KEY")
        topic_id_str = os.environ.get("HCS_TOPIC_ID")

        missing = [
            name
            for name, value in (
                ("HEDERA_ACCOUNT_ID", account_id_str),
                ("HEDERA_PRIVATE_KEY", private_key_str),
                ("HCS_TOPIC_ID", topic_id_str),
            )
            if not value
        ]
        if missing:
            raise HcsConfigError(
                "Missing required env var(s): "
                + ", ".join(missing)
                + ". Create a topic once with HcsLogger.create_topic() and "
                "set HCS_TOPIC_ID — see README.md > Environment Variables."
            )

        try:
            account_id = AccountId.from_string(account_id_str)
            private_key = PrivateKey.from_string(private_key_str)
            topic_id = TopicId.from_string(topic_id_str)
        except Exception as exc:  # pragma: no cover - defensive, SDK-specific
            raise HcsConfigError(f"Invalid Hedera credentials or topic id: {exc}") from exc

        client = Client.for_testnet()
        client.set_operator(account_id, private_key)
        return cls(account_id=account_id, private_key=private_key, client=client, topic_id=topic_id)

    @staticmethod
    def create_topic(account_id: AccountId, private_key: PrivateKey, client: Client, memo: str = "RIA audit trail") -> str:
        """One-time setup: create the HCS topic AUDIT will write to.

        Returns the new topic id (e.g. "0.0.123456") — set this as
        `HCS_TOPIC_ID` for subsequent runs. Deliberately not called by
        `from_env()`, so a topic (and its tiny creation fee) is never
        created as a side effect of just constructing a logger.
        """
        tx = TopicCreateTransaction().set_memo(memo)
        tx.freeze_with(client)
        tx.sign(private_key)
        receipt = tx.execute(client)
        if receipt.topic_id is None:  # pragma: no cover - defensive
            raise HcsSubmitError(f"Topic creation receipt had no topic_id: {receipt}")
        return str(receipt.topic_id)

    @staticmethod
    def _content_hash(event: dict[str, Any]) -> str:
        canonical = json.dumps(event, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def log_payment(
        self,
        *,
        tool_name: str,
        hbar_amount: float,
        hedera_tx_id: str,
        response_hash: str | None = None,
    ) -> dict[str, Any]:
        """Log one x402 payment per README's payment-flow step 8: tool name,
        HBAR amount, Hedera tx ID, response hash -> HCS topic.

        Returns the submit result (consensus tx id + topic sequence
        number) so the caller can build a HashScan/mirror-node link.
        """
        return self.log_event(
            {
                "type": "PAYMENT",
                "tool_name": tool_name,
                "hbar_amount": hbar_amount,
                "hedera_tx_id": hedera_tx_id,
                "response_hash": response_hash,
            }
        )

    def log_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Submit an arbitrary AUDIT event (PAYMENT, EXEC action, ...) to HCS.

        Every entry carries a `content_hash` (sha256 of the rest of the
        payload) so a mirror-node reader can verify the message wasn't
        altered in transit before it reached consensus.
        """
        entry = {**event, "content_hash": self._content_hash(event)}
        message = json.dumps(entry, sort_keys=True, default=str).encode()

        tx = TopicMessageSubmitTransaction().set_topic_id(self.topic_id).set_message(message)
        tx.freeze_with(self.client)
        tx.sign(self.private_key)

        try:
            receipt = tx.execute(self.client)
        except Exception as exc:
            raise HcsSubmitError(f"Failed to submit HCS message: {exc}") from exc

        logger.info(
            "hcs_logger: submitted '%s' event to topic %s (seq %s)",
            event.get("type", "?"),
            self.topic_id,
            getattr(receipt, "topic_sequence_number", None),
        )
        return {
            "topic_id": str(self.topic_id),
            "consensus_tx_id": str(receipt.transaction_id) if receipt.transaction_id else None,
            "topic_sequence_number": receipt.topic_sequence_number,
            "content_hash": entry["content_hash"],
        }


__all__ = ["HcsLogger", "HcsConfigError", "HcsSubmitError"]
