"""`get_price_feed(token)` — 0.0005 HBAR per call.

Data source: CoinGecko's simple/price endpoint (free tier, 30 calls/min) —
see README.md > "Priced tools".
"""

from __future__ import annotations

import os
from typing import Any

import httpx

COINGECKO_API_BASE = "https://api.coingecko.com/api/v3/simple/price"

# token symbol -> CoinGecko coin id, for the assets RIA's signals cover today.
TOKEN_COINGECKO_IDS: dict[str, str] = {
    "ETH": "ethereum",
    "WETH": "weth",
    "WBTC": "wrapped-bitcoin",
    "USDC": "usd-coin",
    "USDT": "tether",
    "DAI": "dai",
    "HBAR": "hedera-hashgraph",
}


class PriceFeedError(RuntimeError):
    """Raised on an unknown token symbol or an API error."""


async def get_price_feed(token: str) -> dict[str, Any]:
    """Spot USD price + 24h change for `token` (a symbol, e.g. "ETH")."""
    symbol = token.upper()
    coin_id = TOKEN_COINGECKO_IDS.get(symbol)
    if coin_id is None:
        known = ", ".join(sorted(TOKEN_COINGECKO_IDS))
        raise PriceFeedError(f"Unknown token '{token}'. Known: {known}")

    params: dict[str, str] = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    # CoinGecko's free tier works without a key; a demo key (if set) raises
    # the rate limit, so pass it through when present rather than requiring it.
    api_key = os.environ.get("COINGECKO_API_KEY")
    if api_key:
        params["x_cg_demo_api_key"] = api_key

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(COINGECKO_API_BASE, params=params)

    if response.status_code != 200:
        raise PriceFeedError(f"CoinGecko returned HTTP {response.status_code}: {response.text[:300]}")

    body = response.json()
    if coin_id not in body:
        raise PriceFeedError(f"CoinGecko response missing '{coin_id}': {body}")

    entry = body[coin_id]
    return {
        "token": symbol,
        "usd": float(entry["usd"]),
        "usd_24h_change": float(entry.get("usd_24h_change", 0.0)),
    }
