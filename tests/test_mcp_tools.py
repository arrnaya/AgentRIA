"""Tests for the 5 priced MCP tools (mcp_server/tools/*.py).

No live credentials, no network: httpx calls (Etherscan, CoinGecko) are
mocked with respx like test_subgraph_client.py; the Anthropic client is
injected as a mock for the LLM-backed tools (sentiment, risk_score).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

import mcp_server.tools.price_feed as price_feed_module
from mcp_server.tools.gas_price import ETHERSCAN_API_BASE, GasPriceError, get_gas_price
from mcp_server.tools.liquidation_stream import LiquidationStreamError, stream_liquidation_alerts
from mcp_server.tools.price_feed import COINGECKO_API_BASE, PriceFeedError, get_price_feed
from mcp_server.tools.risk_score import RiskScoreError, get_risk_score
from mcp_server.tools.sentiment import SentimentError, get_sentiment


@pytest.fixture(autouse=True)
def _clear_price_cache():
    """get_price_feed caches by coin id at module scope (see its own
    docstring for why) -- without this, one test's cached price leaks into
    the next test that queries the same token, silently skipping its mocked
    HTTP response."""
    price_feed_module._price_cache.clear()
    yield
    price_feed_module._price_cache.clear()


# ---------------------------------------------------------------------------
# get_gas_price
# ---------------------------------------------------------------------------


def test_gas_price_requires_api_key(monkeypatch):
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    with pytest.raises(GasPriceError, match="ETHERSCAN_API_KEY"):
        import asyncio

        asyncio.run(get_gas_price("ethereum"))


@respx.mock
async def test_gas_price_returns_parsed_data(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(ETHERSCAN_API_BASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "message": "OK",
                "result": {
                    "LastBlock": "12345",
                    "SafeGasPrice": "10",
                    "ProposeGasPrice": "12",
                    "FastGasPrice": "15",
                    "suggestBaseFee": "9.5",
                },
            },
        )
    )
    result = await get_gas_price("ethereum")
    assert result["network"] == "ethereum"
    assert result["safe_gwei"] == 10.0
    assert result["fast_gwei"] == 15.0
    assert result["last_block"] == 12345


async def test_gas_price_unsupported_network(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    with pytest.raises(GasPriceError, match="Unsupported network"):
        await get_gas_price("not-a-real-network")


@respx.mock
async def test_gas_price_api_error_raises(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(ETHERSCAN_API_BASE).mock(
        return_value=httpx.Response(200, json={"status": "0", "message": "NOTOK", "result": "bad key"})
    )
    with pytest.raises(GasPriceError, match="Etherscan gas oracle error"):
        await get_gas_price("ethereum")


# ---------------------------------------------------------------------------
# get_price_feed
# ---------------------------------------------------------------------------


@respx.mock
async def test_price_feed_returns_parsed_data():
    respx.get(COINGECKO_API_BASE).mock(
        return_value=httpx.Response(200, json={"ethereum": {"usd": 2500.5, "usd_24h_change": -1.2}})
    )
    result = await get_price_feed("ETH")
    assert result["token"] == "ETH"
    assert result["usd"] == 2500.5
    assert result["usd_24h_change"] == -1.2


async def test_price_feed_unknown_token():
    with pytest.raises(PriceFeedError, match="Unknown token"):
        await get_price_feed("NOTATOKEN")


@respx.mock
async def test_price_feed_http_error():
    respx.get(COINGECKO_API_BASE).mock(return_value=httpx.Response(500, text="server error"))
    with pytest.raises(PriceFeedError, match="HTTP 500"):
        await get_price_feed("ETH")


@respx.mock
async def test_price_feed_caches_within_ttl():
    """Regression coverage for a real live-run problem: get_risk_score calls
    this on every enrichment, defaulting to ETH, and a real pipeline cycle
    genuinely exceeded CoinGecko's free tier. A second call for the same
    token within the TTL must reuse the cached result, not hit the network
    again."""
    route = respx.get(COINGECKO_API_BASE).mock(
        return_value=httpx.Response(200, json={"ethereum": {"usd": 2500.5, "usd_24h_change": -1.2}})
    )

    first = await get_price_feed("ETH")
    second = await get_price_feed("eth")  # case-insensitive, same coin id

    assert first == second
    assert route.call_count == 1


@respx.mock
async def test_price_feed_refetches_after_ttl_expires(monkeypatch):
    route = respx.get(COINGECKO_API_BASE).mock(
        return_value=httpx.Response(200, json={"ethereum": {"usd": 2500.5, "usd_24h_change": -1.2}})
    )
    await get_price_feed("ETH")
    assert route.call_count == 1

    # Simulate the TTL having elapsed without a real sleep.
    monkeypatch.setattr(price_feed_module, "PRICE_CACHE_TTL_SECONDS", -1.0)
    await get_price_feed("ETH")
    assert route.call_count == 2


@respx.mock
async def test_price_feed_retries_429_then_succeeds(monkeypatch):
    """The other half of the same regression: a 429 on a cache miss must not
    immediately burn the caller's already-settled x402 payment -- it should
    retry (bounded) before giving up."""
    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(price_feed_module.asyncio, "sleep", _fake_sleep)

    route = respx.get(COINGECKO_API_BASE)
    route.side_effect = [
        httpx.Response(429, text="rate limited"),
        httpx.Response(200, json={"ethereum": {"usd": 2500.5, "usd_24h_change": -1.2}}),
    ]

    result = await get_price_feed("ETH")

    assert result["usd"] == 2500.5
    assert route.call_count == 2
    assert sleep_calls == [price_feed_module.DEFAULT_RETRY_BACKOFF_SECONDS]


@respx.mock
async def test_price_feed_honors_retry_after_header(monkeypatch):
    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(price_feed_module.asyncio, "sleep", _fake_sleep)

    route = respx.get(COINGECKO_API_BASE)
    route.side_effect = [
        httpx.Response(429, text="rate limited", headers={"retry-after": "3"}),
        httpx.Response(200, json={"ethereum": {"usd": 2500.5, "usd_24h_change": -1.2}}),
    ]

    await get_price_feed("ETH")

    assert sleep_calls == [3.0]


@respx.mock
async def test_price_feed_raises_after_exhausting_retries(monkeypatch):
    async def _fake_sleep(seconds):
        pass

    monkeypatch.setattr(price_feed_module.asyncio, "sleep", _fake_sleep)
    respx.get(COINGECKO_API_BASE).mock(return_value=httpx.Response(429, text="rate limited"))

    with pytest.raises(PriceFeedError, match="rate-limited"):
        await get_price_feed("ETH")


# ---------------------------------------------------------------------------
# get_sentiment
# ---------------------------------------------------------------------------


def _fake_anthropic_client(reply_text: str) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = reply_text
    response = MagicMock()
    response.content = [text_block]

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_sentiment_parses_json_score():
    client = _fake_anthropic_client('{"score": 0.75, "reason": "bullish signals"}')
    result = await get_sentiment("uniswap", client=client)
    assert result["protocol"] == "uniswap"
    assert result["score"] == 0.75
    client.messages.create.assert_awaited_once()


async def test_sentiment_clamps_out_of_range_score():
    client = _fake_anthropic_client('{"score": 1.5}')
    result = await get_sentiment("aave", client=client)
    assert result["score"] == 1.0


async def test_sentiment_falls_back_to_bare_number():
    client = _fake_anthropic_client("I'd say around 0.42 given the context.")
    result = await get_sentiment("curve", client=client)
    assert result["score"] == 0.42


async def test_sentiment_unparseable_raises():
    client = _fake_anthropic_client("no numbers here at all")
    with pytest.raises(SentimentError, match="Could not parse"):
        await get_sentiment("curve", client=client)


def test_sentiment_requires_api_key_without_injected_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SentimentError, match="ANTHROPIC_API_KEY"):
        import asyncio

        asyncio.run(get_sentiment("uniswap"))


# ---------------------------------------------------------------------------
# get_risk_score
# ---------------------------------------------------------------------------


@respx.mock
async def test_risk_score_composes_gas_price_and_llm(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(ETHERSCAN_API_BASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "message": "OK",
                "result": {
                    "LastBlock": "1",
                    "SafeGasPrice": "10",
                    "ProposeGasPrice": "12",
                    "FastGasPrice": "15",
                    "suggestBaseFee": "9.5",
                },
            },
        )
    )
    respx.get(COINGECKO_API_BASE).mock(
        return_value=httpx.Response(200, json={"ethereum": {"usd": 2500.0, "usd_24h_change": 0.5}})
    )
    client = _fake_anthropic_client('{"confidence_delta": 0.3, "reason": "healthy conditions"}')

    result = await get_risk_score({"id": "dex:pool1", "type": "yield_gap"}, client=client)

    assert result["opportunity_id"] == "dex:pool1"
    assert result["confidence_delta"] == 0.3
    assert result["gas"]["fast_gwei"] == 15.0
    assert result["price"]["usd"] == 2500.0


async def test_risk_score_clamps_delta():
    # Bypass the gas/price composition by monkeypatching the module funcs
    import mcp_server.tools.risk_score as rs_module

    async def fake_gas(network):
        return {"network": network}

    async def fake_price(token):
        return {"token": token}

    orig_gas, orig_price = rs_module.get_gas_price, rs_module.get_price_feed
    rs_module.get_gas_price = fake_gas
    rs_module.get_price_feed = fake_price
    try:
        client = _fake_anthropic_client('{"confidence_delta": -5}')
        result = await get_risk_score({"id": "x"}, client=client)
        assert result["confidence_delta"] == -1.0
    finally:
        rs_module.get_gas_price = orig_gas
        rs_module.get_price_feed = orig_price


# ---------------------------------------------------------------------------
# stream_liquidation_alerts
# ---------------------------------------------------------------------------


async def test_liquidation_stream_raises_when_substreams_client_missing():
    with pytest.raises(LiquidationStreamError, match="substreams_client is not available"):
        await stream_liquidation_alerts("aave", threshold=0.9)
