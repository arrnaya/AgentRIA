"""`get_gas_price(network)` — 0.0005 HBAR per call.

Data source: Etherscan's Gas Tracker (free tier, 5 calls/sec) — see
README.md > "Priced tools". Etherscan's V2 API is multi-chain via a
`chainid` query param; NETWORK_CHAIN_IDS is the subset RIA supports today.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

ETHERSCAN_API_BASE = "https://api.etherscan.io/v2/api"

# Etherscan V2 chain ids for the networks RIA's signals currently cover.
NETWORK_CHAIN_IDS: dict[str, int] = {
    "ethereum": 1,
}


class GasPriceError(RuntimeError):
    """Raised on missing config, an unsupported network, or an API error."""


async def get_gas_price(network: str = "ethereum") -> dict[str, Any]:
    """Current gas price + EIP-1559 base fee for `network`.

    Returns a dict with safe/propose/fast gas prices (gwei) and the
    suggested EIP-1559 base fee (gwei), straight from Etherscan's oracle.
    """
    api_key = os.environ.get("ETHERSCAN_API_KEY")
    if not api_key:
        raise GasPriceError(
            "ETHERSCAN_API_KEY is not set. Get a free key from "
            "etherscan.io/apis — see README.md > Environment Variables."
        )

    chain_id = NETWORK_CHAIN_IDS.get(network)
    if chain_id is None:
        known = ", ".join(sorted(NETWORK_CHAIN_IDS))
        raise GasPriceError(f"Unsupported network '{network}'. Known: {known}")

    params = {
        "chainid": chain_id,
        "module": "gastracker",
        "action": "gasoracle",
        "apikey": api_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(ETHERSCAN_API_BASE, params=params)

    if response.status_code != 200:
        raise GasPriceError(f"Etherscan returned HTTP {response.status_code}: {response.text[:300]}")

    body = response.json()
    if body.get("status") != "1":
        raise GasPriceError(f"Etherscan gas oracle error: {body.get('message')} — {body.get('result')}")

    result = body["result"]
    return {
        "network": network,
        "safe_gwei": float(result["SafeGasPrice"]),
        "propose_gwei": float(result["ProposeGasPrice"]),
        "fast_gwei": float(result["FastGasPrice"]),
        "suggest_base_fee_gwei": float(result["suggestBaseFee"]),
        "last_block": int(result["LastBlock"]),
    }
