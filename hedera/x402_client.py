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
"HTTP/SSE mode", but SSE's session handshake doesn't fit a simple
402-then-retry request/response exchange. This client targets a plain
JSON-RPC POST endpoint (run the server with `MCP_TRANSPORT=streamable-http`
for this client to work against it) rather than re-implementing MCP's full
session protocol — out of scope for a payment-flow demo.
"""

from __future__ import annotations

import base64
import itertools
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from hedera.wallet import HederaWallet
from hiero_sdk_python import AccountId, TransactionId, TransferTransaction

logger = logging.getLogger("ria.x402_client")

X402_VERSION = 2
PAYMENT_HEADER = "X-PAYMENT"
SETTLEMENT_HEADER = "X-PAYMENT-RESPONSE"
TINYBARS_PER_HBAR = 100_000_000

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

    def _client(self) -> httpx.AsyncClient:
        return self.http_client or httpx.AsyncClient(timeout=15.0)

    async def _maybe_close(self, client: httpx.AsyncClient) -> None:
        if self.http_client is None:
            await client.aclose()

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
    def _parse_rpc_response(response: httpx.Response) -> dict[str, Any]:
        body = response.json()
        if isinstance(body, dict) and body.get("error"):
            raise X402PaymentError(f"MCP tool call returned an error: {body['error']}")
        return body.get("result", body) if isinstance(body, dict) else body

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
            first = await client.post(self.mcp_url, json=self._rpc_envelope(tool_name, arguments))

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
                headers={PAYMENT_HEADER: payment_header},
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
