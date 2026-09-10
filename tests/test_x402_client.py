"""Tests for hedera/x402_client.py — no live credentials, no network.

The MCP server side is mocked with respx (like test_subgraph_client.py).
The Hedera transaction building/signing itself uses *real*
hiero_sdk_python objects with a locally generated ECDSA key — freezing
and signing a TransferTransaction is pure local crypto, no network call,
so exercising the real SDK here (rather than mocking it) catches
integration bugs the middleware tests can't.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx
from hiero_sdk_python import AccountId, Client, PrivateKey, Transaction

from hedera.wallet import HederaWallet
from hedera.x402_client import (
    PAYMENT_HEADER,
    SETTLEMENT_HEADER,
    X402Client,
    X402PaymentError,
)

MCP_URL = "https://mcp.test/mcp"
PAY_TO = "0.0.9999"
FEE_PAYER = "0.0.5555"
BUYER_ACCOUNT = "0.0.1111"


@pytest.fixture
def wallet() -> HederaWallet:
    account_id = AccountId.from_string(BUYER_ACCOUNT)
    private_key = PrivateKey.generate_ecdsa()
    client = Client.for_testnet()  # never actually submits anything in these tests
    return HederaWallet(account_id=account_id, private_key=private_key, client=client)


def _rpc_result_response(payload: dict, extra_headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": payload},
        headers=extra_headers or {},
    )


def _requirements(amount: str = "200000") -> dict:
    return {
        "scheme": "exact",
        "network": "hedera:testnet",
        "amount": amount,
        "asset": "0.0.0",
        "payTo": PAY_TO,
        "maxTimeoutSeconds": 180,
        "extra": {"feePayer": FEE_PAYER},
    }


@respx.mock
async def test_free_tool_call_needs_no_payment(wallet):
    respx.post(MCP_URL).mock(return_value=_rpc_result_response({"ok": True}))
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)

    result = await client.call_tool("get_gas_price", {"network": "ethereum"})

    assert result.result == {"ok": True}
    assert result.settlement is None
    assert result.hbar_paid == 0.0


@respx.mock
async def test_paid_tool_builds_signs_and_retries_with_payment(wallet):
    challenge_body = {"x402Version": 2, "error": "payment required", "accepts": [_requirements()]}
    settlement = {
        "success": True,
        "transactionId": f"{FEE_PAYER}@1700000000.000000000",
        "network": "hedera:testnet",
        "payer": BUYER_ACCOUNT,
    }
    settlement_header = base64.b64encode(json.dumps(settlement).encode()).decode()

    route = respx.post(MCP_URL)
    route.side_effect = [
        httpx.Response(402, json=challenge_body),
        _rpc_result_response({"confidence_delta": 0.3}, extra_headers={SETTLEMENT_HEADER: settlement_header}),
    ]

    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    result = await client.call_tool("get_risk_score", {"opportunity": {"id": "x"}})

    assert result.result == {"confidence_delta": 0.3}
    assert result.settlement == settlement
    assert result.hbar_paid == pytest.approx(0.002)  # 200_000 tinybars

    # The second call carried a well-formed X-PAYMENT header.
    assert route.call_count == 2
    second_request = route.calls[1].request
    payment_header = second_request.headers[PAYMENT_HEADER]
    payload = json.loads(base64.b64decode(payment_header))
    assert payload["x402Version"] == 2
    assert payload["accepted"]["payTo"] == PAY_TO
    assert "transaction" in payload["payload"]

    # The encoded transaction is a real, valid, partially-signed Hedera
    # TransferTransaction: fee payer is the transactionId.accountId, and
    # it carries the buyer's signature (but not the fee payer's).
    tx_bytes = base64.b64decode(payload["payload"]["transaction"])
    restored = Transaction.from_bytes(tx_bytes)
    assert str(restored.transaction_id.account_id) == FEE_PAYER
    assert restored.is_signed_by(wallet.private_key.public_key())


@respx.mock
async def test_paying_own_account_raises_clear_error(wallet):
    """Regression test for a real live-run failure: when payTo (the
    resource server's HEDERA_ACCOUNT_ID) equals this wallet's own account,
    a native Hedera transfer to "yourself" nets to zero -- the facilitator
    rejected this with the fairly opaque
    "invalid_exact_hedera_payload_amount_mismatch". This must be caught
    client-side with an explanation, before ever building the (necessarily
    broken) transaction."""
    requirements = _requirements()
    requirements["payTo"] = BUYER_ACCOUNT  # same account as `wallet` fixture
    respx.post(MCP_URL).mock(
        return_value=httpx.Response(402, json={"x402Version": 2, "accepts": [requirements]})
    )
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    with pytest.raises(X402PaymentError, match="own account"):
        await client.call_tool("get_gas_price")


@respx.mock
async def test_402_with_no_accepts_raises(wallet):
    respx.post(MCP_URL).mock(return_value=httpx.Response(402, json={"x402Version": 2, "accepts": []}))
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    with pytest.raises(X402PaymentError, match="no 'accepts'"):
        await client.call_tool("get_gas_price")


@respx.mock
async def test_unexpected_status_raises(wallet):
    respx.post(MCP_URL).mock(return_value=httpx.Response(500, text="server error"))
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    with pytest.raises(X402PaymentError, match="Unexpected status"):
        await client.call_tool("get_gas_price")


@respx.mock
async def test_payment_retry_rejected_raises(wallet):
    route = respx.post(MCP_URL)
    route.side_effect = [
        httpx.Response(402, json={"x402Version": 2, "accepts": [_requirements()]}),
        httpx.Response(402, json={"x402Version": 2, "error": "invalid_signature", "accepts": [_requirements()]}),
    ]
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    with pytest.raises(X402PaymentError, match="Payment retry"):
        await client.call_tool("get_gas_price")


@respx.mock
async def test_rpc_error_result_raises(wallet):
    respx.post(MCP_URL).mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "boom"}})
    )
    client = X402Client(wallet=wallet, mcp_url=MCP_URL)
    with pytest.raises(X402PaymentError, match="MCP tool call returned an error"):
        await client.call_tool("get_gas_price")
