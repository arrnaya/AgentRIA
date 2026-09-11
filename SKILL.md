---
name: messari-standardized-subgraphs
description: This skill should be used when an agent needs live, normalized DeFi protocol data (liquidity pools, lending markets, TVL, volume, rates) from The Graph's decentralized network — querying Uniswap, Aave, Compound, Curve, or any other protocol that implements a Messari Standardized Subgraph, through one shared GraphQL query shape instead of a bespoke integration per protocol. Also use this skill when a Graph Gateway query fails with "subgraph not found" for an id that used to work — that means the pinned deployment id has gone stale and needs re-deriving from source, not just retrying.
version: 1.0.0
---

# Messari Standardized Subgraphs — one query, many protocols

Extracted from [RIA (Reconnaissance Intelligence Agent)](https://github.com/arrnaya/AgentRIA), built
for ETHGlobal Online 2026's Graph track. RIA's RECON agent uses exactly this pattern, live, against
real Uniswap v3 and Aave v3 deployments on Ethereum mainnet — see `graph/subgraph_client.py`,
`graph/queries/messari.py`, and `agents/recon.py` in that repo for the full working implementation
this skill is distilled from.

## Why this matters

Every DeFi protocol has its own contracts, events, and bespoke subgraph schema — normally, adding a
new protocol to an agent means writing a new indexer or a new bespoke query. **Messari Standardized
Subgraphs** solve this for two whole verticals: every DEX-shaped protocol (Uniswap v3, Curve, ...)
exposes the same `LiquidityPool` entity shape, and every lending-shaped protocol (Aave v3, Compound
v3, ...) exposes the same `Market` entity shape. One GraphQL query, run against N different
`subgraph_id`s, covers N protocols. That composability — Subgraph Studio (the query layer) +
Messari Standardized Subgraphs (the shared schema layer) — is the core of what this skill packages.

## The query pattern

Every request goes to the same Graph Gateway URL shape, with only the `API_KEY` and `SUBGRAPH_ID`
changing:

```
POST https://gateway.thegraph.com/api/<API_KEY>/subgraphs/id/<SUBGRAPH_ID>
Content-Type: application/json

{"query": "<graphql>", "variables": {...}}
```

- `API_KEY` — free from [Subgraph Studio](https://thegraph.com/studio/). One key covers every
  subgraph on the decentralized network; no per-protocol signup.
- `SUBGRAPH_ID` — a specific deployment's id on the decentralized network (e.g.
  `4cKy6QQMc5tpfdx8yxfYeb9TLZmgLQe44ddW1G7NwkA6` for Uniswap v3 Ethereum). **Pin exact ids, don't
  resolve by name** — see "Finding a current subgraph id" below for why this is the single most
  important operational lesson in this skill.
- The gateway returns HTTP 200 even for a GraphQL-level failure (e.g. `subgraph not found`) — the
  error lives in the response body's `errors` array, not the HTTP status. Always check both.

### DEX-vertical query (LiquidityPool entities)

```graphql
query DexPools($first: Int!) {
  liquidityPools(first: $first, orderBy: totalValueLockedUSD, orderDirection: desc) {
    id
    name
    inputTokens { symbol }
    totalValueLockedUSD
    cumulativeVolumeUSD
    fees { feePercentage feeType }
  }
}
```

### Lending-vertical query (Market entities)

```graphql
query LendingMarkets($first: Int!) {
  markets(first: $first, orderBy: totalValueLockedUSD, orderDirection: desc) {
    id
    name
    inputToken { symbol }
    totalValueLockedUSD
    totalDepositBalanceUSD
    totalBorrowBalanceUSD
    rates { rate side type }
  }
}
```

Run the DEX query against any DEX-shaped deployment id and the lending query against any
lending-shaped one — the field names are identical across protocols because Messari's schema is
identical across protocols. Before trusting a new deployment against these exact field names, run
a schema introspection probe (`{ __schema { queryType { fields { name } } } }`) once — deployments
occasionally lag the spec on niche fields.

## Finding a current subgraph id — don't trust a cached one

**This is the lesson this skill exists to save you from re-learning the hard way.** Subgraph
deployment ids are not permanent: protocols get redeployed (schema migrations, indexer changes),
and a perfectly valid-looking id can start returning `subgraph not found` from the Gateway with no
other warning. This happened in RIA's own live pipeline run — two ids that had been correct when
first pinned had gone stale by the time of a real run months later.

The fix is not to guess a new id or search randomly — go to the source:

1. Fetch Messari's own deployment registry: `https://raw.githubusercontent.com/messari/subgraphs/master/deployment/deployment.json`
2. Find the protocol's entry (e.g. `uniswap-v3` → `deployments` → `uniswap-v3-ethereum`)
3. Read `services.decentralized-network.query-id` — that's the current, correct Graph Gateway
   subgraph id.
4. **Cross-check it's actually live**, don't just trust the registry file: fetch
   `https://thegraph.com/explorer/subgraphs/<id>` and confirm it shows real signal and active
   indexing (a 404 or zero signal means even the registry has gone stale for that entry too).

```bash
curl -s https://raw.githubusercontent.com/messari/subgraphs/master/deployment/deployment.json \
  | jq '."uniswap-v3".deployments."uniswap-v3-ethereum".services."decentralized-network"."query-id"'
```

## Minimal Python client

```python
import httpx

GATEWAY_BASE_URL = "https://gateway.thegraph.com/api"

async def query_subgraph(api_key: str, subgraph_id: str, query: str, variables: dict | None = None) -> dict:
    url = f"{GATEWAY_BASE_URL}/{api_key}/subgraphs/id/{subgraph_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json={"query": query, "variables": variables or {}})

    if response.status_code != 200:
        raise RuntimeError(f"Gateway HTTP {response.status_code}: {response.text[:300]}")
    body = response.json()
    if "errors" in body:
        # HTTP 200 does not mean success -- always check this.
        raise RuntimeError(f"GraphQL error: {body['errors']}")
    return body["data"]
```

## Extending to more protocols

Adding a protocol is a one-line addition, not a new integration: look up its current
`decentralized-network` id the same way (steps above), add `{"<slug>": "<id>"}` to your id map, and
reuse whichever of the two query shapes matches its vertical (DEX or lending). RIA's own
`graph/subgraph_client.py` structures this as exactly that — a `SUBGRAPH_IDS: dict[str, str]`
lookup table plus one shared `query()` method, with new protocols added by extending the dict, not
by writing new client code.
