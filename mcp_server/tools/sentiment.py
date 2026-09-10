"""`get_sentiment(protocol)` — 0.001 HBAR per call.

Data source: LLM synthesis over recent on-chain signal context via the
Anthropic API — see README.md > "Priced tools". This module owns only the
LLM call; the "recent on-chain signals" text is passed in by the caller
(ORACLE has already pulled RECON's signals for the protocol) rather than
re-fetched here, to keep this tool a pure paid-compute step.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import AsyncAnthropic

# Sonnet, per README.md > Tech Stack ("Claude Sonnet via Anthropic API" for
# all 6 agents + LLM inference inside MCP tools) — deliberately not the
# priciest model: this runs per paid tool call, at a fraction-of-a-cent
# HBAR price, so the LLM cost has to stay well under the price charged.
MODEL_ID = "claude-sonnet-5"

_SCORE_RE = re.compile(r"-?\d+(?:\.\d+)?")


class SentimentError(RuntimeError):
    """Raised on missing config or an unparseable/failed LLM response."""


def _extract_score(text: str) -> float:
    """Pull a 0-1 float out of the model's reply, tolerating stray prose."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "score" in parsed:
            return max(0.0, min(1.0, float(parsed["score"])))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    match = _SCORE_RE.search(text)
    if not match:
        raise SentimentError(f"Could not parse a sentiment score from LLM reply: {text!r}")
    return max(0.0, min(1.0, float(match.group())))


async def get_sentiment(
    protocol: str,
    context: str = "",
    client: AsyncAnthropic | None = None,
) -> dict[str, Any]:
    """Sentiment score (0-1) for `protocol`, synthesized by Claude.

    `context` is optional free text (recent signal summaries, headlines)
    the caller supplies; with none, the model reasons from its own
    knowledge of the protocol and says so implicitly via a lower score.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SentimentError(
                "ANTHROPIC_API_KEY is not set. Get one from "
                "console.anthropic.com — see README.md > Environment Variables."
            )
        client = AsyncAnthropic()

    prompt = (
        f"Rate the current market sentiment for the DeFi protocol '{protocol}' "
        "on a 0.0 (extremely negative) to 1.0 (extremely positive) scale.\n\n"
    )
    if context:
        prompt += f"Recent on-chain signal context:\n{context}\n\n"
    prompt += 'Respond with ONLY a JSON object: {"score": <float 0-1>, "reason": "<one sentence>"}'

    response = await client.messages.create(
        model=MODEL_ID,
        max_tokens=256,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    score = _extract_score(text)

    return {"protocol": protocol, "score": score, "raw_response": text}
