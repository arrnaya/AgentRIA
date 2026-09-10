from unittest.mock import MagicMock

import pytest

from agents.audit import run_audit
from hedera.hcs_logger import HcsConfigError, HcsSubmitError
from pipeline.state import RiaState


def _action(signal_id: str) -> dict:
    return {
        "signal_id": signal_id,
        "protocol": "Aave v3",
        "network": "ethereum",
        "type": "liquidation_proximity",
        "position_size_usd": 100.0,
        "confidence": 0.9,
        "enrichment_tool": "get_risk_score",
        "enrichment_tx_id": "tx-1",
        "status": "dispatched",
        "dispatched_at": "2026-09-10T00:00:00+00:00",
    }


def _mock_hcs(topic_id: str = "0.0.999", consensus_tx_id: str = "0.0.999@1.2") -> MagicMock:
    hcs = MagicMock()
    hcs.log_payment.return_value = {
        "topic_id": topic_id,
        "consensus_tx_id": consensus_tx_id,
        "topic_sequence_number": 1,
        "content_hash": "deadbeef",
    }
    return hcs


async def test_run_audit_logs_dispatched_actions():
    state = RiaState()
    state.actions = [_action("sig-1")]
    state.enrichments = [
        {"signal_id": "sig-1", "tool": "get_risk_score", "hbar_cost": 0.002, "tx_id": "tx-1", "raw_response": "ok"}
    ]
    hcs = _mock_hcs()

    result = await run_audit(state, logger_client=hcs)

    assert result is state
    assert len(state.audit_entries) == 1
    entry = state.audit_entries[0]
    assert entry["signal_id"] == "sig-1"
    assert entry["hcs_topic_id"] == "0.0.999"
    assert entry["tx_id"] == "0.0.999@1.2"
    hcs.log_payment.assert_called_once()
    _, kwargs = hcs.log_payment.call_args
    assert kwargs["tool_name"] == "get_risk_score"
    assert kwargs["hbar_amount"] == 0.002
    assert kwargs["hedera_tx_id"] == "tx-1"
    assert kwargs["response_hash"] is not None


async def test_run_audit_skips_already_audited_actions():
    state = RiaState()
    state.actions = [_action("sig-1")]
    state.audit_entries = [{"signal_id": "sig-1"}]
    hcs = _mock_hcs()

    await run_audit(state, logger_client=hcs)

    hcs.log_payment.assert_not_called()
    assert len(state.audit_entries) == 1


async def test_run_audit_handles_missing_enrichment_gracefully():
    state = RiaState()
    state.actions = [_action("sig-1")]  # no matching entry in state.enrichments
    hcs = _mock_hcs()

    await run_audit(state, logger_client=hcs)

    _, kwargs = hcs.log_payment.call_args
    assert kwargs["tool_name"] == "unknown"
    assert kwargs["hbar_amount"] == 0.0
    assert kwargs["hedera_tx_id"] == ""
    assert kwargs["response_hash"] is None


async def test_run_audit_continues_past_a_failed_submission():
    state = RiaState()
    state.actions = [_action("sig-1"), _action("sig-2")]
    hcs = _mock_hcs()
    hcs.log_payment.side_effect = [
        HcsSubmitError("mirror node unreachable"),
        {"topic_id": "0.0.999", "consensus_tx_id": "tx-ok", "topic_sequence_number": 2, "content_hash": "abc"},
    ]

    await run_audit(state, logger_client=hcs)

    assert len(state.audit_entries) == 1
    assert state.audit_entries[0]["signal_id"] == "sig-2"


async def test_run_audit_skips_gracefully_with_no_topic_configured(monkeypatch):
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HEDERA_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("HCS_TOPIC_ID", raising=False)
    state = RiaState()
    state.actions = [_action("sig-1")]

    result = await run_audit(state)

    assert result is state
    assert state.audit_entries == []


async def test_run_audit_noop_with_no_actions():
    state = RiaState()

    result = await run_audit(state)

    assert result is state
    assert state.audit_entries == []
