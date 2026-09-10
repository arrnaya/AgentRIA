"""`get_risk_score(opportunity)` — 0.002 HBAR per call, the main SKU.

Data source: LLM inference over gas + price + position data — see
README.md > "Priced tools". This composes the two cheaper tools
(`get_gas_price`, `get_price_feed`) internally and feeds their output plus
the caller's position data into Claude for a risk-adjusted confidence
delta, so a single `get_risk_score` call buys strictly more than calling
the two underlying tools separately would.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import AsyncAnthropic

from mcp_server.tools.gas_price import GasPriceError, get_gas_price
from mcp_server.tools.price_feed import PriceFeedError, get_price_feed

MODEL_ID = "claude-sonnet-5"  # see sentiment.py for the model-choice rationale

_DELTA_RE = re.compile(r"-?\d+(?:\.\d+)?")


class RiskScoreError(RuntimeError):
    """Raised on missing config or an unparseable/failed LLM response."""


def _extract_delta(text: str) -> float:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "confidence_delta" in parsed:
            return max(-1.0, min(1.0, float(parsed["confidence_delta"])))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    match = _DELTA_RE.search(text)
    if not match:
        raise RiskScoreError(f"Could not parse a confidence delta from LLM reply: {text!r}")
    return max(-1.0, min(1.0, float(match.group())))


async def get_risk_score(
    opportunity: dict[str, Any],
    network: str = "ethereum",
    token: str = "ETH",
    client: AsyncAnthropic | None = None,
) -> dict[str, Any]:
    """Risk-adjusted confidence delta (-1..1) for `opportunity`.

    `opportunity` is expected to look like `OpportunitySignal`/
    `RankedOpportunity` from `pipeline.state` (protocol, type, raw_metrics,
    rank_score, ...) — passed as a plain dict so this tool has no import
    dependency on the pipeline package.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RiskScoreError(
                "ANTHROPIC_API_KEY is not set. Get one from "
                "console.anthropic.com — see README.md > Environment Variables."
            )
        client = AsyncAnthropic()

    try:
        gas = await get_gas_price(network)
    except GasPriceError as exc:
        raise RiskScoreError(f"get_risk_score: gas price lookup failed: {exc}") from exc

    try:
        price = await get_price_feed(token)
    except PriceFeedError as exc:
        raise RiskScoreError(f"get_risk_score: price feed lookup failed: {exc}") from exc

    prompt = (
        "You are a DeFi risk analyst. Given the opportunity signal, current "
        "gas conditions, and current spot price below, output a risk-adjusted "
        "confidence delta: how much should the raw signal confidence be "
        "adjusted, from -1.0 (much riskier than it looks) to +1.0 (much safer "
        "than it looks), 0.0 meaning no adjustment.\n\n"
        f"Opportunity: {json.dumps(opportunity, default=str)}\n"
        f"Gas ({network}): {json.dumps(gas)}\n"
        f"Price ({token}): {json.dumps(price)}\n\n"
        'Respond with ONLY a JSON object: {"confidence_delta": <float -1..1>, "reason": "<one sentence>"}'
    )

    response = await client.messages.create(
        model=MODEL_ID,
        max_tokens=300,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    delta = _extract_delta(text)

    return {
        "opportunity_id": opportunity.get("id"),
        "confidence_delta": delta,
        "gas": gas,
        "price": price,
        "raw_response": text,
    }
