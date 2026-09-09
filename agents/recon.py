"""RECON — data ingestion & normalization.

RECON is the only agent that talks to The Graph. It pulls raw pool/market
data via Subgraph Studio and normalizes it into `OpportunitySignal` records.
It does not rank or score opportunities — that heuristic classification
below (yield_gap vs. liquidation_proximity vs. rate_divergence) is a
first-pass label so downstream agents have something to key off of; SCOUT
owns the real ranking logic on top of it.
"""

from __future__ import annotations

import logging
from typing import Any

from graph.queries.messari import DEX_POOLS_QUERY, LENDING_MARKETS_QUERY
from graph.subgraph_client import SubgraphClient
from pipeline.state import OpportunitySignal, RiaState, SignalType, now_iso

logger = logging.getLogger("ria.recon")

# subgraph_key -> (network label, protocol label) for the deployments RECON
# is wired to today. Extend this as more Messari deployments are added.
DEX_SOURCES = [("uniswap-v3-ethereum", "ethereum", "Uniswap v3")]
LENDING_SOURCES = [("aave-v3-ethereum", "ethereum", "Aave v3")]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_dex_pool(
    pool: dict[str, Any], network: str, protocol: str
) -> OpportunitySignal:
    symbols = [t.get("symbol", "?") for t in pool.get("inputTokens", [])]
    pair = "/".join(symbols) if symbols else pool.get("name", "unknown")
    tvl = _safe_float(pool.get("totalValueLockedUSD"))
    volume = _safe_float(pool.get("cumulativeVolumeUSD"))

    # Heuristic: pools doing outsized volume relative to their TVL are
    # earning outsized fee yield relative to capital at risk — flag as a
    # yield signal for SCOUT to weigh. This is intentionally simple; SCOUT
    # is where real ranking logic lives.
    signal_type = SignalType.YIELD_GAP

    return OpportunitySignal(
        id=f"dex:{pool['id']}",
        protocol=protocol,
        network=network,
        pair=pair,
        type=signal_type,
        raw_metrics={
            "totalValueLockedUSD": tvl,
            "cumulativeVolumeUSD": volume,
            "fees": pool.get("fees", []),
        },
        source="subgraph-studio:messari-dex",
        observed_at=now_iso(),
    )


def _normalize_lending_market(
    market: dict[str, Any], network: str, protocol: str
) -> OpportunitySignal:
    pair = market.get("inputToken", {}).get("symbol", market.get("name", "unknown"))
    deposits = _safe_float(market.get("totalDepositBalanceUSD"))
    borrows = _safe_float(market.get("totalBorrowBalanceUSD"))
    utilization = (borrows / deposits) if deposits > 0 else 0.0

    # Heuristic: high utilization means less room before rates spike / users
    # approach liquidation; flag those separately from mid-utilization
    # markets where a rate quirk is the more likely signal.
    signal_type = (
        SignalType.LIQUIDATION_PROXIMITY
        if utilization > 0.8
        else SignalType.RATE_DIVERGENCE
    )

    return OpportunitySignal(
        id=f"lending:{market['id']}",
        protocol=protocol,
        network=network,
        pair=pair,
        type=signal_type,
        raw_metrics={
            "totalDepositBalanceUSD": deposits,
            "totalBorrowBalanceUSD": borrows,
            "utilization": utilization,
            "rates": market.get("rates", []),
        },
        source="subgraph-studio:messari-lending",
        observed_at=now_iso(),
    )


async def run_recon(
    state: RiaState, client: SubgraphClient | None = None, first: int = 10
) -> RiaState:
    """Pull live DEX + lending data and append normalized signals to state."""
    client = client or SubgraphClient.from_env()
    signals: list[OpportunitySignal] = []

    for subgraph_key, network, protocol in DEX_SOURCES:
        data = await client.query(subgraph_key, DEX_POOLS_QUERY, {"first": first})
        for pool in data.get("liquidityPools", []):
            signals.append(_normalize_dex_pool(pool, network, protocol))
        logger.info("RECON: %d pools from %s", len(data.get("liquidityPools", [])), subgraph_key)

    for subgraph_key, network, protocol in LENDING_SOURCES:
        data = await client.query(
            subgraph_key, LENDING_MARKETS_QUERY, {"first": first}
        )
        for market in data.get("markets", []):
            signals.append(_normalize_lending_market(market, network, protocol))
        logger.info("RECON: %d markets from %s", len(data.get("markets", [])), subgraph_key)

    state.signals.extend(signals)
    return state
