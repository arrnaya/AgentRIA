from unittest.mock import AsyncMock

import pytest

from agents.oracle import run_oracle
from hedera.wallet import WalletConfigError
from hedera.x402_client import ToolCallResult, X402PaymentError
from pipeline.state import RiaState


def _signal(signal_id: str, protocol: str = "Aave v3") -> dict:
    return {
        "id": signal_id,
        "protocol": protocol,
        "network": "ethereum",
        "pair": "USDC",
        "type": "liquidation_proximity",
        "raw_metrics": {},
        "source": "test",
        "observed_at": "2026-09-10T00:00:00+00:00",
    }


def _assessment(signal_id: str, above_threshold: bool = True) -> dict:
    return {
        "opportunity": {"signal": _signal(signal_id), "rank_score": 0.9},
        "confidence": 0.8,
        "position_size_usd": 100.0,
        "above_threshold": above_threshold,
    }


def _mock_client(hbar_paid: float = 0.002, tx_id: str = "0.0.1@123.456") -> AsyncMock:
    client = AsyncMock()
    client.call_tool.return_value = ToolCallResult(
        result={"confidence_delta": 0.1, "raw_response": "ok"},
        settlement={"transactionId": tx_id},
        hbar_paid=hbar_paid,
    )
    return client


async def test_run_oracle_enriches_above_threshold_assessments():
    state = RiaState(budget_hbar=10.0)
    state.assessments = [_assessment("sig-1"), _assessment("sig-2", above_threshold=False)]
    client = _mock_client()

    result = await run_oracle(state, client=client)

    assert result is state
    assert len(state.enrichments) == 1
    enrichment = state.enrichments[0]
    assert enrichment["signal_id"] == "sig-1"
    assert enrichment["tool"] == "get_risk_score"
    assert enrichment["confidence_delta"] == 0.1
    assert enrichment["hbar_cost"] == 0.002
    assert enrichment["tx_id"] == "0.0.1@123.456"
    assert state.hbar_spent == 0.002
    client.call_tool.assert_awaited_once_with("get_risk_score", {"opportunity": _signal("sig-1")})


async def test_run_oracle_skips_already_enriched_signals():
    state = RiaState()
    state.assessments = [_assessment("sig-1")]
    state.enrichments = [{"signal_id": "sig-1", "tool": "get_risk_score", "hbar_cost": 0.0}]
    client = _mock_client()

    await run_oracle(state, client=client)

    client.call_tool.assert_not_awaited()
    assert len(state.enrichments) == 1


async def test_run_oracle_stops_when_budget_exhausted():
    state = RiaState(budget_hbar=0.001)  # less than one get_risk_score call (0.002)
    state.assessments = [_assessment("sig-1")]
    client = _mock_client()

    await run_oracle(state, client=client)

    client.call_tool.assert_not_awaited()
    assert state.enrichments == []


async def test_run_oracle_continues_past_a_failed_payment():
    state = RiaState(budget_hbar=10.0)
    state.assessments = [_assessment("sig-1"), _assessment("sig-2")]
    client = AsyncMock()
    client.call_tool.side_effect = [
        X402PaymentError("facilitator rejected payment"),
        ToolCallResult(result={"confidence_delta": 0.2}, settlement={"transactionId": "tx-2"}, hbar_paid=0.002),
    ]

    await run_oracle(state, client=client)

    assert len(state.enrichments) == 1
    assert state.enrichments[0]["signal_id"] == "sig-2"


async def test_run_oracle_skips_gracefully_with_no_wallet(monkeypatch):
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    state = RiaState()
    state.assessments = [_assessment("sig-1")]

    result = await run_oracle(state)

    assert result is state
    assert state.enrichments == []


async def test_run_oracle_noop_with_no_above_threshold_assessments():
    state = RiaState()
    state.assessments = [_assessment("sig-1", above_threshold=False)]

    result = await run_oracle(state)

    assert result is state
    assert state.enrichments == []
