"""`get_price_feed(token)` — 0.0005 HBAR per call.

Data source: CoinGecko's simple/price endpoint (free tier, 30 calls/min) —
see README.md > "Priced tools".

Rate-limit discipline: `get_risk_score` (mcp_server/tools/risk_score.py)
calls this internally on every enrichment, defaulting to ETH -- and a real
live pipeline run confirmed this genuinely exceeds CoinGecko's free tier
(repeated `429 Too Many Requests`) once ORACLE is enriching several signals
a cycle. Worse than just noisy logs: the x402 middleware settles payment
*before* the tool executes, so a 429 here used to mean real, non-refundable
HBAR spent on a failed enrichment. Fixed two ways:

  1. A short in-memory TTL cache per coin id -- ETH's price does not need
     sub-minute freshness for a risk-scoring LLM prompt, and most calls in
     a pipeline cycle are for the same token, so this cuts real request
     volume by roughly the enrichment count per cache window, not just by
     a fixed percentage.
  2. A small bounded retry with backoff specifically for 429 (honoring a
     `Retry-After` header if CoinGecko sends one), so a cache-miss that
     still gets rate-limited doesn't waste the already-settled payment on
     a single transient blip.
"""

from __future__ import annotations

import asyncio
import os
import time
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

# See module docstring for why these exist. 60s is short enough that a
# genuine price move within a pipeline run is never stale by more than one
# cycle interval; long enough to collapse an entire cycle's worth of
# same-token enrichments into a single real CoinGecko call.
PRICE_CACHE_TTL_SECONDS = 60.0
MAX_RATE_LIMIT_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 5.0

# coin_id -> (cached_at monotonic seconds, result). Process-local and
# unbounded by design -- TOKEN_COINGECKO_IDS is a small fixed set, so this
# can never grow past a handful of entries.
_price_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class PriceFeedError(RuntimeError):
    """Raised on an unknown token symbol or an API error."""


def _cached(coin_id: str) -> dict[str, Any] | None:
    entry = _price_cache.get(coin_id)
    if entry is None:
        return None
    cached_at, result = entry
    if time.monotonic() - cached_at >= PRICE_CACHE_TTL_SECONDS:
        return None
    return result


async def get_price_feed(token: str) -> dict[str, Any]:
    """Spot USD price + 24h change for `token` (a symbol, e.g. "ETH")."""
    symbol = token.upper()
    coin_id = TOKEN_COINGECKO_IDS.get(symbol)
    if coin_id is None:
        known = ", ".join(sorted(TOKEN_COINGECKO_IDS))
        raise PriceFeedError(f"Unknown token '{token}'. Known: {known}")

    cached = _cached(coin_id)
    if cached is not None:
        return cached

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

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(COINGECKO_API_BASE, params=params)

        if response.status_code == 429:
            if attempt < MAX_RATE_LIMIT_RETRIES:
                retry_after = response.headers.get("retry-after", "")
                delay = float(retry_after) if retry_after.isdigit() else DEFAULT_RETRY_BACKOFF_SECONDS
                await asyncio.sleep(delay)
                continue
            raise PriceFeedError(
                f"CoinGecko rate-limited (429) for '{coin_id}' after {MAX_RATE_LIMIT_RETRIES} "
                "retries -- free tier exceeded"
            )

        if response.status_code != 200:
            raise PriceFeedError(f"CoinGecko returned HTTP {response.status_code}: {response.text[:300]}")

        body = response.json()
        if coin_id not in body:
            raise PriceFeedError(f"CoinGecko response missing '{coin_id}': {body}")

        entry = body[coin_id]
        result = {
            "token": symbol,
            "usd": float(entry["usd"]),
            "usd_24h_change": float(entry.get("usd_24h_change", 0.0)),
        }
        _price_cache[coin_id] = (time.monotonic(), result)
        return result

    raise AssertionError("unreachable")  # pragma: no cover - loop always returns or raises above
