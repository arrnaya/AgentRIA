"""LIVE Hedera TESTNET demo — an independent third-party agent paying RIA's
x402-gated MCP server, spending real (free, testnet-only) HBAR.

This is deliberately NOT `hedera/x402_client.py` used through
`agents/oracle.py` / `pipeline/runner.py` — it's the same open client
library, but run standalone, with its own wallet, never touching RIA's
pipeline state. That's the entire point: proving the MCP server is a
generalized commercial primitive any MCP-compatible agent can pay to use,
not something only RIA's own ORACLE can talk to. See README.md's Demo
Strategy / DEMO_SCRIPT.md's 2:20-2:40 segment.

Standalone, like `scripts/live_smoke_test.py`: not run by `pytest`, not
wired into CI, needs credentials this agent is deliberately not given
access to. Run it yourself; it never fabricates a transaction id or
HashScan link — if any step fails, it prints the real error and exits
non-zero.

Requires, in the environment (never read from a `.env*` file directly):

  - HEDERA_ACCOUNT_ID / HEDERA_PRIVATE_KEY — a funded Hedera TESTNET
    account. For the demo to be convincing, use a THIRD account here --
    not ORACLE's own wallet, not the MCP server's payTo account. Paying
    from ORACLE's own wallet would still work, but wouldn't demonstrate
    anything an "external agent" claim needs: a genuinely different payer.

Run (with the MCP server already running in streamable-http mode --
see scripts/live_smoke_test.py's docstring for that half):

    export HEDERA_ACCOUNT_ID=0.0.xxxxx
    export HEDERA_PRIVATE_KEY=...
    python scripts/external_agent_demo.py

Calls each of the four tools that actually work end-to-end today
(get_gas_price, get_sentiment, get_price_feed, get_risk_score) once each,
real payment each time. `stream_liquidation_alerts` is deliberately
skipped and explained, not silently omitted -- it depends on
`graph.substreams_client`, which doesn't exist (Substreams was scoped out
for time; see README.md's Build Timeline). Calling it would still settle
a real, non-refundable payment before failing, which is exactly the
CoinGecko-429 lesson this build already paid for once
(mcp_server/tools/price_feed.py's docstring) -- not repeating it here for
a call known in advance to fail.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Make the repo root importable when this script is run directly
# (`python scripts/external_agent_demo.py`) rather than as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hedera.wallet import HederaWallet, WalletConfigError  # noqa: E402
from hedera.x402_client import X402Client, X402PaymentError  # noqa: E402

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")

# A representative opportunity shape (mirrors pipeline.state.OpportunitySignal
# well enough for get_risk_score's prompt-building, per its own docstring:
# "passed as a plain dict so this tool has no import dependency on the
# pipeline package"). Not a real signal RECON produced -- this script never
# touches the pipeline -- but a realistic stand-in, clearly labeled as such.
DEMO_OPPORTUNITY = {
    "id": "demo:external-agent-uniswap-v3",
    "protocol": "Uniswap v3",
    "network": "ethereum",
    "pair": "WETH/USDC",
    "type": "yield_gap",
    "raw_metrics": {"totalValueLockedUSD": 8_500_000.0, "cumulativeVolumeUSD": 32_000_000.0},
}


def _hashscan_url(tx_id: str) -> str:
    if "@" not in tx_id:
        return f"https://hashscan.io/testnet/transaction/{tx_id}"
    account, ts = tx_id.split("@", 1)
    seconds, _, nanos = ts.partition(".")
    return f"https://hashscan.io/testnet/transaction/{account}-{seconds}-{nanos}"


async def _call(client: X402Client, tool_name: str, arguments: dict) -> bool:
    print(f"\n--- {tool_name}({', '.join(f'{k}={v!r}' for k, v in arguments.items())}) ---")
    try:
        outcome = await client.call_tool(tool_name, arguments)
    except X402PaymentError as exc:
        print(f"FAILED: {exc}")
        return False

    print(f"Result: {outcome.result}")
    print(f"HBAR paid: {outcome.hbar_paid}")
    if outcome.settlement:
        tx_id = outcome.settlement.get("transactionId") or outcome.settlement.get("transaction")
        if tx_id:
            print(f"Settlement tx: {tx_id}")
            print(f"HashScan: {_hashscan_url(tx_id)}")
    return True


async def main() -> int:
    print("=== RIA external-agent x402 demo (Hedera TESTNET) ===")
    print(f"MCP server: {MCP_URL}")
    print("This wallet has never interacted with RIA's own pipeline.\n")

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

    calls = [
        ("get_gas_price", {"network": "ethereum"}),
        ("get_sentiment", {"protocol": "Uniswap v3"}),
        ("get_price_feed", {"token": "ETH"}),
        ("get_risk_score", {"opportunity": DEMO_OPPORTUNITY}),
    ]

    results = []
    for tool_name, arguments in calls:
        results.append(await _call(client, tool_name, arguments))

    print(
        "\n--- stream_liquidation_alerts SKIPPED: depends on graph.substreams_client, "
        "which doesn't exist yet (Substreams scoped out for time, see README.md's "
        "Build Timeline). Calling it would settle a real payment before failing -- "
        "not worth spending real HBAR on a call known in advance to fail. ---"
    )

    passed = sum(results)
    print(f"\n=== {passed}/{len(calls)} tools called successfully, real payment each time ===")
    return 0 if passed == len(calls) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
