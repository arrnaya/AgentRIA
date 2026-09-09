"""GraphQL query templates against Messari Standardized Subgraphs.

Field names follow the Messari subgraph schema (github.com/messari/subgraphs)
shared across every DEX and lending protocol that implements it — this is
what lets RECON run the *same* query shape against Uniswap, Aave, Compound,
and Curve. Verify field names against a live introspection query once a real
GRAPH_API_KEY is available (see graph/subgraph_client.py:introspect) —
subgraph deployments occasionally lag the spec on niche fields.
"""

# DEX-vertical schema (Uniswap v3, Curve, ...): entities are LiquidityPools.
DEX_POOLS_QUERY = """
query DexPools($first: Int!) {
  liquidityPools(
    first: $first
    orderBy: totalValueLockedUSD
    orderDirection: desc
  ) {
    id
    name
    inputTokens {
      symbol
    }
    totalValueLockedUSD
    cumulativeVolumeUSD
    fees {
      feePercentage
      feeType
    }
  }
}
"""

# Lending-vertical schema (Aave v3, Compound v3, ...): entities are Markets.
LENDING_MARKETS_QUERY = """
query LendingMarkets($first: Int!) {
  markets(
    first: $first
    orderBy: totalValueLockedUSD
    orderDirection: desc
  ) {
    id
    name
    inputToken {
      symbol
    }
    totalValueLockedUSD
    totalDepositBalanceUSD
    totalBorrowBalanceUSD
    rates {
      rate
      side
      type
    }
  }
}
"""

# Introspection probe used to confirm a deployment matches the schema shape
# this client expects before RECON relies on it in a live run.
SCHEMA_PROBE_QUERY = """
query SchemaProbe {
  __schema {
    queryType {
      fields {
        name
      }
    }
  }
}
"""
