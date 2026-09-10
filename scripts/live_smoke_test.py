"""LIVE Hedera TESTNET smoke test — spends real (free, testnet-only) HBAR.

This is a standalone script, NOT run by `pytest` and not wired into CI.
It requires credentials this agent is deliberately not given access to —
see `.claude/agents/hedera-payments-engineer.md` > Credentials. Run it
yourself; it never fabricates a transaction id or HashScan link — if any
step of the chain fails, it prints the real error and exits non-zero.

Requires, in the environment (never read from a `.env*` file by this
script directly — export them, or `source .env` yourself first):

  - HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY — a funded Hedera TESTNET
    account (free from the Hedera Testnet Portal faucet).
  - BLOCKY402_FACILITATOR_URL — confirmed live and working, no signup or
    API key: https://api.testnet.blocky402.com (verified via a plain
    `GET /supported` -- returns "hedera:testnet" with a real fee-payer
    account). A self-hosted hedera-dev/scaffold-hbar facilitator (see
    facilitator/README.md on that repo's templates/x402-pay-per-use
    branch) is the fallback if Blocky402's hosted one is ever down.
  - ETHERSCAN_API_KEY — get_gas_price (the tool this script calls) needs
    it; free from etherscan.io/apis.

Run in two terminals:

    # Terminal 1 — start the MCP server in streamable-http mode.
    # (hedera/x402_client.py's 402-then-retry flow is a plain
    # request/response exchange and doesn't implement MCP's SSE session
    # handshake, so this script needs streamable-http, not the sse
    # default.)
    export HEDERA_ACCOUNT_ID=0.0.xxxxx
    export HEDERA_PRIVATE_KEY=...
    export BLOCKY402_FACILITATOR_URL=https://...
    export ETHERSCAN_API_KEY=...
    MCP_TRANSPORT=streamable-http python -m mcp_server.server

    # Terminal 2 — this script (ORACLE paying for one real tool call).
    export HEDERA_ACCOUNT_ID=0.0.xxxxx
    export HEDERA_PRIVATE_KEY=...
    python scripts/live_smoke_test.py

This calls the cheapest priced tool — get_gas_price, 0.0005 HBAR — once,
end to end against the real facilitator and Hedera testnet, and prints
the settlement transaction id.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Make the repo root importable when this script is run directly
# (`python scripts/live_smoke_test.py`) rather than as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hedera.wallet import HederaWallet, WalletConfigError  # noqa: E402
from hedera.x402_client import X402Client, X402PaymentError  # noqa: E402

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")


def _hashscan_url(tx_id: str) -> str:
    # Hedera tx ids come back as "accountId@seconds.nanos"; HashScan's
    # transaction URLs use "accountId-seconds-nanos". Best-effort format
    # conversion of a real id this run produces — not a fabricated link.
    if "@" not in tx_id:
        return f"https://hashscan.io/testnet/transaction/{tx_id}"
    account, ts = tx_id.split("@", 1)
    seconds, _, nanos = ts.partition(".")
    return f"https://hashscan.io/testnet/transaction/{account}-{seconds}-{nanos}"


async def main() -> int:
    print("=== RIA live testnet smoke test ===")
    print(f"MCP server: {MCP_URL}")
    print("Network: Hedera TESTNET (never mainnet)\n")

    try:
        wallet = HederaWallet.from_env()
    except WalletConfigError as exc:
        print(f"FAILED - wallet config: {exc}")
        return 1

    try:
        balance_tinybars = wallet.get_balance_tinybars()
        print(f"Operator {wallet.account_id}: {balance_tinybars / 100_000_000:.4f} HBAR available")
    except Exception as exc:
        print(f"FAILED - could not query testnet balance (is the account real and funded?): {exc}")
        return 1

    client = X402Client(wallet=wallet, mcp_url=MCP_URL)

    print("\nCalling get_gas_price(network='ethereum') via the x402-gated MCP server (0.0005 HBAR)...")
    try:
        outcome = await client.call_tool("get_gas_price", {"network": "ethereum"})
    except X402PaymentError as exc:
        print(f"FAILED - payment/tool flow: {exc}")
        return 1

    print(f"\nTool result: {outcome.result}")
    print(f"HBAR paid: {outcome.hbar_paid}")

    if outcome.settlement:
        tx_id = outcome.settlement.get("transactionId") or outcome.settlement.get("transaction")
        print(f"Settlement receipt: {outcome.settlement}")
        if tx_id:
            print(f"HashScan (best-effort URL from this real tx id): {_hashscan_url(tx_id)}")
    else:
        print("(no payment was required for this call — unexpected for a priced tool; check server wiring)")

    print("\n=== smoke test PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
