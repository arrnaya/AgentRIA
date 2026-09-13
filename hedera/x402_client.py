"""ORACLE's side of the x402 payment flow: build a partially-signed Hedera
`TransferTransaction`, retry the MCP tool call with proof of payment.

Containment rule: this module — and `hedera/wallet.py` underneath it — is
the ONLY code in this repo allowed to hold wallet credentials or sign a
transaction. No other agent module (`recon.py`, `scout.py`, `risk.py`,
`exec.py`, `audit.py`) may import `X402Client`.

Flow (README.md > "x402 Payment Flow — Step by Step", steps 1-7; wire
contract verified against x402-foundation/x402's
`specs/schemes/exact/scheme_exact_hedera.md` — see
`mcp_server/x402_middleware.py`'s docstring for the same references):

  1. POST the MCP `tools/call` with no `X-PAYMENT` header.
  2. Server returns HTTP 402 with `PaymentRequirements` (`accepts[0]`).
  3. Build a `TransferTransaction`: this wallet -> `payTo` for `amount`
     tinybars, with `transactionId.accountId` set to
     `extra.feePayer` — the facilitator, not this wallet, pays the
     Hedera network fee (spec section "Protocol Flow", step 3).
  4. Sign with this wallet's key only — a **partially signed**
     transaction. This client never talks to the facilitator or submits
     to Hedera directly; the facilitator adds its fee-payer signature and
     submits at `POST /settle`, server-side, after the resource server
     forwards the payload.
  5. Base64-encode the serialized transaction into
     `PaymentPayload.payload.transaction`.
  6. Base64-encode the full `PaymentPayload` JSON into the `X-PAYMENT`
     header, retry the same tool call.
  7. Server verifies + settles and returns 200 with the tool result and
     an `X-PAYMENT-RESPONSE` header (the settlement receipt) — this is
     what AUDIT logs to HCS via `hedera/hcs_logger.py`.

Note on transport: `mcp_server/server.py` defaults to SSE per README's
"HTTP/SSE mode" (run the server with `MCP_TRANSPORT=streamable-http` for
this client to work against it). Confirmed live against FastMCP's actual
streamable-http implementation (`mcp.server.streamable_http`), this
transport still requires its own session handshake even outside SSE's
GET-stream model: every POST must carry an `Accept: application/json,
text/event-stream` header (else HTTP 406) and, after an `initialize` call,
an `Mcp-Session-Id` header matching what `initialize`'s response returned
(else HTTP 400 "Missing session ID"). Responses come back SSE-framed
(`content-type: text/event-stream`, body `event: message\ndata: {...}`) by
default, not plain JSON. `_ensure_session` and `_parse_response_body`
implement exactly this — the minimum needed for a single request/response
exchange, not the full bidirectional SSE streaming session model.
"""

from __future__ import annotations

import base64
import itertools
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from hedera.wallet import HederaWallet
from hiero_sdk_python import AccountId, TransactionId, TransferTransaction

logger = logging.getLogger("ria.x402_client")

X402_VERSION = 2
PAYMENT_HEADER = "X-PAYMENT"
SETTLEMENT_HEADER = "X-PAYMENT-RESPONSE"
SESSION_HEADER = "Mcp-Session-Id"
TINYBARS_PER_HBAR = 100_000_000

# Streamable-http rejects any request that doesn't advertise both -- see
# this module's docstring.
ACCEPT_HEADER = "application/json, text/event-stream"

_request_id_counter = itertools.count(1)


class X402PaymentError(RuntimeError):
    """Raised when the MCP server rejects the call/payment, or the facilitator
    contract isn't what this client expects."""


@dataclass
class ToolCallResult:
    """What ORACLE gets back from a paid (or free) tool call."""

    result: dict[str, Any]
    settlement: dict[str, Any] | None  # None if the call never needed payment
    hbar_paid: float


@dataclass
class X402Client:
    """ORACLE's x402-paying MCP client — the only agent code that spends HBAR."""

    wallet: HederaWallet
    mcp_url: str
    http_client: httpx.AsyncClient | None = None
    _session_id: str | None = field(default=None, init=False, repr=False)

    def _client(self) -> httpx.AsyncClient:
        return self.http_client or httpx.AsyncClient(timeout=15.0)

    async def _maybe_close(self, client: httpx.AsyncClient) -> None:
        if self.http_client is None:
            await client.aclose()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": ACCEPT_HEADER}
        if self._session_id:
            headers[SESSION_HEADER] = self._session_id
        if extra:
            headers.update(extra)
        return headers

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        """Perform the streamable-http `initialize` handshake once and cache
        the `Mcp-Session-Id` every later request on this client must carry.
        A fresh `X402Client` has none yet -- every real call (paid or free)
        needs one, since both eventually reach FastMCP's streamable handler,
        which 400s with "Missing session ID" without it."""
        if self._session_id:
            return
        envelope = {
            "jsonrpc": "2.0",
            "id": next(_request_id_counter),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ria-oracle", "version": "1.0.0"},
            },
        }
        response = await client.post(self.mcp_url, json=envelope, headers=self._headers())
        if response.status_code != 200:
            raise X402PaymentError(
                f"MCP session initialize failed: HTTP {response.status_code}: {response.text[:300]}"
            )
        session_id = response.headers.get(SESSION_HEADER) or response.headers.get(SESSION_HEADER.lower())
        if not session_id:
            raise X402PaymentError("MCP server did not return an Mcp-Session-Id on initialize")
        self._session_id = session_id

    @staticmethod
    def _rpc_envelope(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": next(_request_id_counter),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

    def _build_payment_header(self, requirements: dict[str, Any]) -> str:
        """Build, partially sign, and encode a `PaymentPayload` for
        `requirements` per `scheme_exact_hedera.md`'s `exact` scheme."""
        amount = int(requirements["amount"])
        pay_to = AccountId.from_string(requirements["payTo"])
        fee_payer = AccountId.from_string(requirements["extra"]["feePayer"])

        if pay_to == self.wallet.account_id:
            # A native Hedera HBAR transfer to yourself always nets to zero
            # -- the network (and hiero_sdk_python locally) collapses two
            # entries for the same account in one TransferList into a
            # single net amount, so this wallet's -amount and pay_to's
            # +amount cancel out before the transaction is ever sent.
            # Confirmed against a real live run: the facilitator's /verify
            # rejected exactly this with
            # "invalid_exact_hedera_payload_amount_mismatch" because it saw
            # 0 tinybars net to payTo, not `amount`. ORACLE's wallet
            # (HEDERA_ACCOUNT_ID) and the resource server's payTo
            # (also HEDERA_ACCOUNT_ID, from X402Middleware.from_env) must be
            # two different funded testnet accounts.
            raise X402PaymentError(
                f"Cannot pay {pay_to}: it's this wallet's own account. A native "
                "Hedera transfer to yourself always nets to zero, so the "
                "facilitator will reject it as an amount mismatch. Run the MCP "
                "server (Terminal 1) with a *different* HEDERA_ACCOUNT_ID than "
                "ORACLE's own wallet (Terminal 2) — it doesn't need a private "
                "key, just a second funded testnet account to receive payments."
            )

        tx = (
            TransferTransaction()
            .add_hbar_transfer(self.wallet.account_id, -amount)
            .add_hbar_transfer(pay_to, amount)
        )
        # The fee payer (facilitator), not this wallet, is the network-level
        # transaction payer — spec section "Protocol Flow", step 3.
        tx.set_transaction_id(TransactionId.generate(fee_payer))
        tx.freeze_with(self.wallet.client)
        tx.sign(self.wallet.private_key)
        tx_bytes = tx.to_bytes()

        payload = {
            "x402Version": X402_VERSION,
            "accepted": requirements,
            "payload": {"transaction": base64.b64encode(tx_bytes).decode()},
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()

    @staticmethod
    def _parse_response_body(response: httpx.Response) -> dict[str, Any]:
        """Parse a JSON-RPC response that may come back as a plain
        `application/json` body or, per this module's docstring, SSE-framed
        (`content-type: text/event-stream`, `event: message\\ndata: {...}`)
        -- FastMCP's default for streamable-http."""
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("text/event-stream"):
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[len("data:") :].strip())
            raise X402PaymentError(f"SSE response from MCP server had no 'data:' event: {response.text[:300]}")
        return response.json()

    @staticmethod
    def _unwrap_tool_content(result: Any) -> Any:
        """FastMCP wraps a tool's own return value in MCP's content envelope
        (`{"content": [{"type": "text", "text": "<json>"}], "isError": ...}`)
        rather than returning it directly. Confirmed via a real live call's
        exact wire shape (a smoke test's own printed output:
        `{'content': [{'type': 'text', 'text': '{"network": ...}'}], ...}`).

        Every caller of `call_tool()` -- agents/oracle.py chief among them --
        expects `ToolCallResult.result` to be the tool's actual return value
        (e.g. `get_risk_score`'s `confidence_delta`/`raw_response` keys
        directly), not this transport-level wrapper. Left unwrapped, `.get()`
        calls against those keys always silently returned the default: this
        real bug shipped a `confidence_delta` of `0.0` for every enrichment
        ever run, and a `raw_response` of `None` (hence AUDIT's HCS entries
        always logging `response_hash: null`) -- undetected because the
        existing tests mocked a flat dict, not the real wire shape.

        Falls back to the raw result unchanged if it doesn't match the
        expected envelope shape, so a tool returning something else (or a
        future FastMCP version with a different envelope) degrades to the
        old behavior rather than crashing.
        """
        if not isinstance(result, dict):
            return result
        content = result.get("content")
        if not (isinstance(content, list) and content):
            return result
        first = content[0]
        if not (isinstance(first, dict) and first.get("type") == "text"):
            return result
        try:
            return json.loads(first["text"])
        except (json.JSONDecodeError, TypeError):
            return result

    @classmethod
    def _parse_rpc_response(cls, response: httpx.Response) -> dict[str, Any]:
        body = cls._parse_response_body(response)
        if isinstance(body, dict) and body.get("error"):
            raise X402PaymentError(f"MCP tool call returned an error: {body['error']}")
        result = body.get("result", body) if isinstance(body, dict) else body
        return cls._unwrap_tool_content(result)

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> ToolCallResult:
        """Call `tool_name`, paying via x402 if (and only if) the server 402s.

        Returns the tool's result and, if a payment was made, the
        facilitator's settlement receipt — AUDIT logs the latter to HCS.
        """
        arguments = arguments or {}
        client = self._client()
        try:
            await self._ensure_session(client)

            first = await client.post(
                self.mcp_url, json=self._rpc_envelope(tool_name, arguments), headers=self._headers()
            )

            if first.status_code == 200:
                return ToolCallResult(result=self._parse_rpc_response(first), settlement=None, hbar_paid=0.0)

            if first.status_code != 402:
                raise X402PaymentError(
                    f"Unexpected status calling '{tool_name}': HTTP {first.status_code}: {first.text[:300]}"
                )

            challenge = first.json()
            accepts = challenge.get("accepts") or []
            if not accepts:
                raise X402PaymentError(f"402 response for '{tool_name}' had no 'accepts': {challenge}")
            requirements = accepts[0]

            payment_header = self._build_payment_header(requirements)

            retry = await client.post(
                self.mcp_url,
                json=self._rpc_envelope(tool_name, arguments),
                headers=self._headers({PAYMENT_HEADER: payment_header}),
            )
            if retry.status_code != 200:
                raise X402PaymentError(
                    f"Payment retry for '{tool_name}' failed: HTTP {retry.status_code}: {retry.text[:300]}"
                )

            result = self._parse_rpc_response(retry)

            settlement = None
            settlement_header = retry.headers.get(SETTLEMENT_HEADER)
            if settlement_header:
                settlement = json.loads(base64.b64decode(settlement_header))

            hbar_paid = int(requirements["amount"]) / TINYBARS_PER_HBAR
            logger.info("x402_client: paid %s HBAR for '%s'", hbar_paid, tool_name)
            return ToolCallResult(result=result, settlement=settlement, hbar_paid=hbar_paid)
        finally:
            await self._maybe_close(client)


__all__ = ["X402Client", "X402PaymentError", "ToolCallResult"]
