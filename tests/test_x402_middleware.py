"""Tests for mcp_server/x402_middleware.py — no live network.

Builds a tiny Starlette app standing in for the MCP transport app, wraps
it in X402Middleware, and drives it with Starlette's TestClient. All
Blocky402 facilitator HTTP calls are mocked with respx — no real
network, no credentials.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_server.x402_middleware import (
    PAYMENT_HEADER,
    SETTLEMENT_HEADER,
    FacilitatorError,
    X402Middleware,
)

FACILITATOR_URL = "https://facilitator.test"
PAY_TO = "0.0.9999"
FEE_PAYER = "0.0.5555"


async def _rpc_endpoint(request: Request) -> JSONResponse:
    body = await request.json()
    return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "result": {"ok": True}})


def _build_client() -> TestClient:
    app = Starlette(routes=[Route("/mcp", _rpc_endpoint, methods=["POST"])])
    app.add_middleware(
        X402Middleware,
        facilitator_url=FACILITATOR_URL,
        pay_to_account_id=PAY_TO,
    )
    return TestClient(app)


def _tools_call_body(tool_name: str, tool_id: int = 1) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": tool_id, "method": "tools/call", "params": {"name": tool_name, "arguments": {}}}
    ).encode()


def _payment_header(transaction_b64: str = "AAAA") -> str:
    payload = {
        "x402Version": 2,
        "accepted": {
            "scheme": "exact",
            "network": "hedera:testnet",
            "amount": "50000",
            "asset": "0.0.0",
            "payTo": PAY_TO,
            "maxTimeoutSeconds": 180,
            "extra": {"feePayer": FEE_PAYER},
        },
        "payload": {"transaction": transaction_b64},
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def test_non_post_passes_through():
    app = Starlette(routes=[Route("/mcp", lambda r: JSONResponse({"ok": True}), methods=["GET"])])
    app.add_middleware(X402Middleware, facilitator_url=FACILITATOR_URL, pay_to_account_id=PAY_TO)
    client = TestClient(app)
    resp = client.get("/mcp")
    assert resp.status_code == 200


def test_non_tools_call_method_passes_through():
    client = _build_client()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    resp = client.post("/mcp", content=body)
    assert resp.status_code == 200
    assert resp.json()["result"] == {"ok": True}


def test_unknown_tool_passes_through_ungated():
    client = _build_client()
    resp = client.post("/mcp", content=_tools_call_body("not_a_priced_tool"))
    assert resp.status_code == 200


@respx.mock
def test_priced_tool_without_payment_returns_402():
    respx.get(f"{FACILITATOR_URL}/supported").mock(
        return_value=httpx.Response(200, json={"signers": {"hedera": [FEE_PAYER]}})
    )
    client = _build_client()
    resp = client.post("/mcp", content=_tools_call_body("get_gas_price"))

    assert resp.status_code == 402
    body = resp.json()
    assert body["x402Version"] == 2
    accepts = body["accepts"][0]
    assert accepts["scheme"] == "exact"
    assert accepts["network"] == "hedera:testnet"
    assert accepts["asset"] == "0.0.0"
    assert accepts["payTo"] == PAY_TO
    assert accepts["amount"] == "50000"  # 0.0005 HBAR in tinybars
    assert accepts["extra"]["feePayer"] == FEE_PAYER


@respx.mock
def test_priced_tool_with_valid_payment_settles_and_forwards():
    respx.get(f"{FACILITATOR_URL}/supported").mock(
        return_value=httpx.Response(200, json={"signers": {"hedera": [FEE_PAYER]}})
    )
    verify_route = respx.post(f"{FACILITATOR_URL}/verify").mock(
        return_value=httpx.Response(200, json={"isValid": True, "payer": "0.0.1111"})
    )
    settle_route = respx.post(f"{FACILITATOR_URL}/settle").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "transactionId": "0.0.5555@1700000000.000000000",
                "network": "hedera:testnet",
                "payer": "0.0.1111",
            },
        )
    )

    client = _build_client()
    resp = client.post(
        "/mcp",
        content=_tools_call_body("get_risk_score"),
        headers={PAYMENT_HEADER: _payment_header()},
    )

    assert resp.status_code == 200
    assert resp.json()["result"] == {"ok": True}
    assert verify_route.called
    assert settle_route.called

    settlement_b64 = resp.headers[SETTLEMENT_HEADER]
    settlement = json.loads(base64.b64decode(settlement_b64))
    assert settlement["transactionId"] == "0.0.5555@1700000000.000000000"

    # /verify and /settle both received the wire shape scaffold-hbar's
    # facilitator expects: {paymentPayload, paymentRequirements}.
    verify_sent = json.loads(verify_route.calls[0].request.content)
    assert set(verify_sent) == {"paymentPayload", "paymentRequirements"}
    assert verify_sent["paymentRequirements"]["amount"] == "200000"  # 0.002 HBAR


@respx.mock
def test_failed_verification_returns_402_with_reason():
    respx.get(f"{FACILITATOR_URL}/supported").mock(
        return_value=httpx.Response(200, json={"signers": {"hedera": [FEE_PAYER]}})
    )
    respx.post(f"{FACILITATOR_URL}/verify").mock(
        return_value=httpx.Response(200, json={"isValid": False, "invalidReason": "bad_signature"})
    )

    client = _build_client()
    resp = client.post(
        "/mcp",
        content=_tools_call_body("get_price_feed"),
        headers={PAYMENT_HEADER: _payment_header()},
    )

    assert resp.status_code == 402
    assert "bad_signature" in resp.json()["error"]


@respx.mock
def test_failed_settlement_returns_402_with_reason():
    respx.get(f"{FACILITATOR_URL}/supported").mock(
        return_value=httpx.Response(200, json={"signers": {"hedera": [FEE_PAYER]}})
    )
    respx.post(f"{FACILITATOR_URL}/verify").mock(return_value=httpx.Response(200, json={"isValid": True}))
    respx.post(f"{FACILITATOR_URL}/settle").mock(
        return_value=httpx.Response(200, json={"success": False, "errorReason": "INSUFFICIENT_BALANCE"})
    )

    client = _build_client()
    resp = client.post(
        "/mcp",
        content=_tools_call_body("get_sentiment"),
        headers={PAYMENT_HEADER: _payment_header()},
    )

    assert resp.status_code == 402
    assert "INSUFFICIENT_BALANCE" in resp.json()["error"]


def test_malformed_payment_header_returns_402():
    with respx.mock:
        respx.get(f"{FACILITATOR_URL}/supported").mock(
            return_value=httpx.Response(200, json={"signers": {"hedera": [FEE_PAYER]}})
        )
        client = _build_client()
        resp = client.post(
            "/mcp",
            content=_tools_call_body("get_gas_price"),
            headers={PAYMENT_HEADER: "not-valid-base64!!"},
        )
        assert resp.status_code == 402


@respx.mock
def test_facilitator_unreachable_returns_503():
    respx.get(f"{FACILITATOR_URL}/supported").mock(return_value=httpx.Response(500, text="boom"))
    client = _build_client()
    resp = client.post("/mcp", content=_tools_call_body("get_gas_price"))
    assert resp.status_code == 503


def test_from_env_requires_config(monkeypatch):
    monkeypatch.delenv("BLOCKY402_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    with pytest.raises(FacilitatorError, match="BLOCKY402_FACILITATOR_URL"):
        X402Middleware.from_env(app=None)


def test_from_env_builds_instance(monkeypatch):
    monkeypatch.setenv("BLOCKY402_FACILITATOR_URL", FACILITATOR_URL)
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", PAY_TO)
    instance = X402Middleware.from_env(app=None)
    assert instance.facilitator_url == FACILITATOR_URL
    assert instance.pay_to_account_id == PAY_TO
    assert instance.network == "hedera:testnet"
