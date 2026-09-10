"""Per-tool HBAR price config for the x402-gated MCP server.

The five tools and their prices are fixed by README.md's "Priced tools"
table — this module is the single source of truth every other module reads
from, so a price never drifts between the middleware, the client, and the
docs. Don't invent new tools or prices here; update the README first.

x402's Hedera `exact` scheme (see
https://github.com/x402-foundation/x402/blob/main/specs/schemes/exact/scheme_exact_hedera.md)
requires `PaymentRequirements.amount` in the asset's smallest unit. For
native HBAR (`asset == "0.0.0"`) that's **tinybars**: 1 HBAR = 10**8
tinybars. `price_tinybars()` is what actually goes on the wire; `price_hbar`
is only for human-readable display (logs, dashboard, docstrings).
"""

from __future__ import annotations

from dataclasses import dataclass

TINYBARS_PER_HBAR = 100_000_000

# The Hedera "asset" identifier for native HBAR under the x402 exact scheme
# (as opposed to an HTS fungible token id like "0.0.xxxxx").
HBAR_ASSET_ID = "0.0.0"


@dataclass(frozen=True)
class ToolPrice:
    """Price for one MCP tool call."""

    tool_name: str
    price_hbar: float
    description: str

    def price_tinybars(self) -> int:
        """Exact wire amount for `PaymentRequirements.amount` (tinybars, as int)."""
        tinybars = round(self.price_hbar * TINYBARS_PER_HBAR)
        if tinybars <= 0:
            raise ValueError(f"{self.tool_name}: price must be > 0 tinybars")
        return tinybars


# README.md > "The Core Innovation — x402-Gated MCP Server" > "Priced tools".
# stream_liquidation_alerts is priced per alert delivered, not per call.
TOOL_PRICES: dict[str, ToolPrice] = {
    "get_gas_price": ToolPrice(
        tool_name="get_gas_price",
        price_hbar=0.0005,
        description="Current gas price + EIP-1559 base fee (Etherscan Gas Tracker)",
    ),
    "get_sentiment": ToolPrice(
        tool_name="get_sentiment",
        price_hbar=0.001,
        description="Sentiment score for a protocol (0-1), LLM synthesis over on-chain signals",
    ),
    "get_risk_score": ToolPrice(
        tool_name="get_risk_score",
        price_hbar=0.002,
        description="Risk-adjusted confidence delta for a signal (the main SKU)",
    ),
    "get_price_feed": ToolPrice(
        tool_name="get_price_feed",
        price_hbar=0.0005,
        description="Spot price + 24h change (CoinGecko)",
    ),
    "stream_liquidation_alerts": ToolPrice(
        tool_name="stream_liquidation_alerts",
        price_hbar=0.001,
        description="Pre-filtered liquidation-proximity alerts (priced per alert)",
    ),
}


class UnknownToolError(KeyError):
    """Raised when pricing is requested for a tool not in TOOL_PRICES."""


def get_price(tool_name: str) -> ToolPrice:
    try:
        return TOOL_PRICES[tool_name]
    except KeyError as exc:
        known = ", ".join(sorted(TOOL_PRICES))
        raise UnknownToolError(
            f"Unknown MCP tool '{tool_name}'. Known tools: {known}"
        ) from exc
