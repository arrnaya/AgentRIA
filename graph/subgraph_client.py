"""Async client for The Graph's decentralized network gateway.

Wraps the Subgraph Studio / Graph Gateway GraphQL endpoint:

    https://gateway.thegraph.com/api/<API_KEY>/subgraphs/id/<SUBGRAPH_ID>

Every RIA query pattern (DEX pools, lending markets) is the *same* query
shape run against different subgraph IDs — that's what "Messari Standardized
Subgraphs" buys RECON: one client, one query per vertical, N protocols.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

GATEWAY_BASE_URL = "https://gateway.thegraph.com/api"

# Messari Standardized Subgraph deployment IDs on the decentralized network.
# Source: The Graph Explorer (thegraph.com/explorer). Pin exact IDs here
# rather than resolving by name so a query never silently starts hitting an
# unvetted deployment.
SUBGRAPH_IDS: dict[str, str] = {
    "uniswap-v3-ethereum": "ELUcwgpm14LKPLrBRuVvPvNKHQ9HvwmtKgKSH6123cr7",
    "aave-v3-ethereum": "HB1Z2EAw4rtPRYVb2Nz8QGFLHCpym6ByBX6vbCViuE9F",
}


class SubgraphQueryError(RuntimeError):
    """Raised when the gateway returns a transport or GraphQL-level error."""


@dataclass
class SubgraphClient:
    """Thin async wrapper around one Graph Gateway API key.

    Raises immediately if no key is configured — RECON has no fallback data
    source, so failing loud here beats a confusing downstream empty result.
    """

    api_key: str
    timeout_s: float = 15.0

    @classmethod
    def from_env(cls) -> "SubgraphClient":
        api_key = os.environ.get("GRAPH_API_KEY")
        if not api_key:
            raise SubgraphQueryError(
                "GRAPH_API_KEY is not set. Get a free key from Subgraph "
                "Studio (https://thegraph.com/studio/) — see README.md "
                "> Environment Variables."
            )
        return cls(api_key=api_key)

    def _endpoint(self, subgraph_key: str) -> str:
        if subgraph_key not in SUBGRAPH_IDS:
            known = ", ".join(sorted(SUBGRAPH_IDS))
            raise SubgraphQueryError(
                f"Unknown subgraph '{subgraph_key}'. Known: {known}"
            )
        subgraph_id = SUBGRAPH_IDS[subgraph_key]
        return f"{GATEWAY_BASE_URL}/{self.api_key}/subgraphs/id/{subgraph_id}"

    async def query(
        self, subgraph_key: str, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run one GraphQL query against a pinned subgraph deployment."""
        url = self._endpoint(subgraph_key)
        payload = {"query": query, "variables": variables or {}}

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            raise SubgraphQueryError(
                f"Gateway returned HTTP {response.status_code} for "
                f"'{subgraph_key}': {response.text[:300]}"
            )

        body = response.json()
        if "errors" in body:
            raise SubgraphQueryError(
                f"GraphQL error querying '{subgraph_key}': {body['errors']}"
            )
        return body["data"]
