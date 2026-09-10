"""LIVE Hedera TESTNET smoke test for AUDIT's HCS writer — spends real
(free, testnet-only) HBAR on network fees.

Standalone, like `scripts/live_smoke_test.py`: not run by `pytest`, not
wired into CI, needs credentials this agent is deliberately not given
access to — see `.claude/agents/hedera-payments-engineer.md` > Credentials.
Run it yourself; it never fabricates a topic id, tx id, or HashScan link —
if any step fails, it prints the real error and exits non-zero.

Requires, in the environment (never read from a `.env*` file directly —
export them, or `source .env` yourself first):

  - HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY — the same funded Hedera
    TESTNET account used for `live_smoke_test.py`. AUDIT and ORACLE run
    against the same operator account today (see hedera/hcs_logger.py's
    docstring) — this is a small, fixed network fee, not the commercial
    x402 payment.
  - HCS_TOPIC_ID — optional. If unset, this script creates a new topic
    (one-time, `HcsLogger.create_topic()`) and prints it so you can save
    it as `HCS_TOPIC_ID` for later runs instead of creating a new topic
    every time.

Run:

    export HEDERA_ACCOUNT_ID=0.0.xxxxx
    export HEDERA_PRIVATE_KEY=...
    # export HCS_TOPIC_ID=0.0.xxxxx   # optional, reuses an existing topic
    python scripts/hcs_smoke_test.py

This creates a topic if needed, then submits one real PAYMENT-shaped
event to it, and prints the topic id, the consensus transaction id, and
HashScan/mirror-node links so the result can be independently verified —
by anyone, not just this script's own claim.
"""

from __future__ import annotations

import os
import sys

# Make the repo root importable when this script is run directly
# (`python scripts/hcs_smoke_test.py`) rather than as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hiero_sdk_python import AccountId, Client  # noqa: E402

from hedera.hcs_logger import HcsConfigError, HcsLogger, HcsSubmitError  # noqa: E402
from hedera.key_loader import KeyLoadError, load_private_key  # noqa: E402


def _topic_hashscan_url(topic_id: str) -> str:
    return f"https://hashscan.io/testnet/topic/{topic_id}"


def _mirror_node_messages_url(topic_id: str) -> str:
    return f"https://testnet.mirrornode.hedera.com/api/v1/topics/{topic_id}/messages"


def main() -> int:
    print("=== RIA live HCS smoke test ===")
    print("Network: Hedera TESTNET (never mainnet)\n")

    account_id_str = os.environ.get("HEDERA_ACCOUNT_ID")
    private_key_str = os.environ.get("HEDERA_PRIVATE_KEY")
    topic_id_str = os.environ.get("HCS_TOPIC_ID")

    missing = [
        name for name, value in (("HEDERA_ACCOUNT_ID", account_id_str), ("HEDERA_PRIVATE_KEY", private_key_str)) if not value
    ]
    if missing:
        print(f"FAILED - missing required env var(s): {', '.join(missing)}")
        return 1

    try:
        account_id = AccountId.from_string(account_id_str)
    except Exception as exc:
        print(f"FAILED - HEDERA_ACCOUNT_ID is not a valid Hedera account id: {exc}")
        return 1

    try:
        private_key = load_private_key(account_id_str, private_key_str)
    except KeyLoadError as exc:
        print(f"FAILED - private key: {exc}")
        return 1

    client = Client.for_testnet()
    client.set_operator(account_id, private_key)

    if topic_id_str:
        print(f"Using existing topic {topic_id_str}")
    else:
        print("No HCS_TOPIC_ID set — creating a new topic (one-time network fee)...")
        try:
            topic_id_str = HcsLogger.create_topic(account_id, private_key, client)
        except HcsSubmitError as exc:
            print(f"FAILED - could not create topic: {exc}")
            return 1
        print(f"Created topic {topic_id_str} — save this as HCS_TOPIC_ID for future runs")

    os.environ["HCS_TOPIC_ID"] = topic_id_str
    try:
        hcs = HcsLogger.from_env()
    except HcsConfigError as exc:
        print(f"FAILED - could not build HcsLogger: {exc}")
        return 1

    print("\nSubmitting one real PAYMENT-shaped event to HCS...")
    try:
        receipt = hcs.log_payment(
            tool_name="get_gas_price",
            hbar_amount=0.0005,
            hedera_tx_id="smoke-test-no-real-payment-tx",
            response_hash=None,
        )
    except HcsSubmitError as exc:
        print(f"FAILED - could not submit HCS message: {exc}")
        return 1

    print(f"\nReceipt: {receipt}")
    print(f"Topic HashScan: {_topic_hashscan_url(topic_id_str)}")
    print(f"Topic messages (mirror node, independently verifiable): {_mirror_node_messages_url(topic_id_str)}")
    print("\n=== HCS smoke test PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
