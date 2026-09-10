"""RIA's x402-gated MCP server (HTTP/SSE mode).

Any MCP-compatible AI agent — Claude, GPT, Gemini, a LangGraph agent, a
CrewAI agent — can connect here and pay per tool call in HBAR on Hedera
testnet via Blocky402. See README.md > "The Core Innovation — x402-Gated
MCP Server" for the full spec; ORACLE (`hedera/x402_client.py`) is the
first consumer, not the only one.

Run:

    python -m mcp_server.server

Requires `BLOCKY402_FACILITATOR_URL` and `HEDERA_ACCOUNT_ID` (the account
tool payments settle to) in the environment — see README.md > Environment
Variables. `MCP_TRANSPORT` selects `sse` (default, per README's "HTTP/SSE
mode") or `streamable-http`; `MCP_HOST` / `MCP_PORT` control the bind
address (defaults `127.0.0.1:8000`).
"""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from mcp_server.pricing import TOOL_PRICES
from mcp_server.tools.gas_price import get_gas_price
from mcp_server.tools.liquidation_stream import stream_liquidation_alerts
from mcp_server.tools.price_feed import get_price_feed
from mcp_server.tools.risk_score import get_risk_score
from mcp_server.tools.sentiment import get_sentiment
from mcp_server.x402_middleware import X402Middleware

logger = logging.getLogger("ria.mcp_server")

mcp = FastMCP(
    name="ria-mcp-server",
    instructions=(
        "RIA's x402-gated DeFi intelligence tools. Every call below is "
        "priced in HBAR on Hedera testnet — call without an X-PAYMENT "
        "header first to receive the HTTP 402 payment requirements, then "
        "retry with a signed, settled payment. See mcp_server.pricing for "
        "exact prices."
    ),
)

# Each tool is registered with `name=` set explicitly to the pricing key
# (mcp_server.pricing.TOOL_PRICES) so the wire-visible MCP tool name is
# exactly what mcp_server.x402_middleware looks up a price for in
# `params.name` — no implicit name derivation to keep in sync by hand.


@mcp.tool(name="get_gas_price", description=TOOL_PRICES["get_gas_price"].description)
async def _get_gas_price(network: str = "ethereum") -> dict:
    return await get_gas_price(network)


@mcp.tool(name="get_sentiment", description=TOOL_PRICES["get_sentiment"].description)
async def _get_sentiment(protocol: str, context: str = "") -> dict:
    return await get_sentiment(protocol, context)


@mcp.tool(name="get_risk_score", description=TOOL_PRICES["get_risk_score"].description)
async def _get_risk_score(opportunity: dict, network: str = "ethereum", token: str = "ETH") -> dict:
    return await get_risk_score(opportunity, network=network, token=token)


@mcp.tool(name="get_price_feed", description=TOOL_PRICES["get_price_feed"].description)
async def _get_price_feed(token: str) -> dict:
    return await get_price_feed(token)


@mcp.tool(
    name="stream_liquidation_alerts",
    description=TOOL_PRICES["stream_liquidation_alerts"].description,
)
async def _stream_liquidation_alerts(protocol: str, threshold: float = 0.8) -> dict:
    return await stream_liquidation_alerts(protocol, threshold)


def build_app():
    """Build the ASGI app: the FastMCP transport app wrapped in x402 gating."""
    transport = os.environ.get("MCP_TRANSPORT", "sse")
    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()

    # X402Middleware.from_env(app=None) here only to validate + read config;
    # Starlette's add_middleware constructs the real instance lazily so it
    # can slot it correctly into the ASGI middleware stack.
    config = X402Middleware.from_env(app=None)
    app.add_middleware(
        X402Middleware,
        facilitator_url=config.facilitator_url,
        pay_to_account_id=config.pay_to_account_id,
        network=config.network,
    )
    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    app = build_app()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))
    logger.info("RIA x402-gated MCP server listening on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
