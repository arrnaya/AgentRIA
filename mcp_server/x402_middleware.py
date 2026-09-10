"""Blocky402 payment verification middleware for the x402-gated MCP server.

Gates every MCP JSON-RPC `tools/call` request behind a confirmed HBAR
payment on Hedera testnet, per README.md > "x402 Payment Flow — Step by
Step": no `X-PAYMENT` header (or a failed `/verify`/`/settle`) -> HTTP 402
with payment instructions; a settled payment -> the request is forwarded
to the underlying MCP app and the tool executes.

Wire contract confirmed directly against ground truth, not guessed:
- The x402 Hedera "exact" scheme spec
  (x402-foundation/x402, specs/schemes/exact/scheme_exact_hedera.md) —
  `PaymentRequirements` / `PaymentPayload` / `SettlementResponse` shapes,
  the partially-signed `TransferTransaction` flow (buyer signs, facilitator
  co-signs as `extra.feePayer` and submits), and the facilitator
  verification rules (transfer must net exactly `amount` to `payTo`, fee
  payer never a net sender, etc.).
- `hedera-dev/scaffold-hbar`'s reference facilitator
  (`facilitator/src/server.ts`, branch `templates/x402-pay-per-use`) — the
  actual `POST /verify` and `POST /settle` request bodies a facilitator
  expects: `{ paymentPayload, paymentRequirements }`, and `GET /supported`
  advertising the fee-payer account under `signers`.
- Blocky402's own site (blocky402.com) confirms Hedera testnet is "fully
  operational, open access — no API key required" and describes the
  client-facing `X-PAYMENT` header / HTTP 402 flow, but does not publish
  endpoint-level request/response JSON. This middleware implements the
  x402-foundation spec and scaffold-hbar's reference shape, which
  Blocky402 (an independent, spec-compliant Hedera facilitator) accepts.

Known gap, handled defensively: the `x402` PyPI package's own
`SettleResponse` dataclass (`x402.facilitator_base`) serializes the
settled tx id under the key `transaction`, while the canonical Hedera
exact-scheme spec's example `SettlementResponse` uses `transactionId`.
This module reads the facilitator's raw JSON directly and accepts either
key rather than trusting the python package's field aliases.

Billing note: `stream_liquidation_alerts` is priced *per alert* in
`mcp_server.pricing`, but this middleware settles one payment per
`tools/call` request, not per alert in the response — see
`mcp_server/tools/liquidation_stream.py`'s docstring for the same caveat.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_server.pricing import HBAR_ASSET_ID, UnknownToolError, get_price

logger = logging.getLogger("ria.x402_middleware")

X402_VERSION = 2
PAYMENT_HEADER = "X-PAYMENT"
SETTLEMENT_HEADER = "X-PAYMENT-RESPONSE"
DEFAULT_NETWORK = "hedera:testnet"


class FacilitatorError(RuntimeError):
    """Raised when the Blocky402 facilitator is unreachable, misconfigured,
    or rejects a payment (missing config also raises this, since a
    misconfigured middleware can't gate anything correctly)."""


class X402Middleware(BaseHTTPMiddleware):
    """Starlette ASGI middleware gating MCP `tools/call` behind x402 payment.

    Wraps the ASGI app returned by `FastMCP.sse_app()` /
    `.streamable_http_app()`. Only JSON-RPC `tools/call` requests naming a
    tool in `mcp_server.pricing.TOOL_PRICES` are gated — `initialize`,
    `tools/list`, etc. pass straight through so a client can discover the
    tool schema (and its price) before paying for anything.
    """

    def __init__(
        self,
        app,
        *,
        facilitator_url: str,
        pay_to_account_id: str,
        network: str = DEFAULT_NETWORK,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(app)
        self.facilitator_url = facilitator_url.rstrip("/")
        self.pay_to_account_id = pay_to_account_id
        self.network = network
        # Tests inject a mocked client; production lets each call open (and
        # close) its own short-lived httpx.AsyncClient.
        self._http_client = http_client
        self._fee_payer: str | None = None

    @classmethod
    def from_env(cls, app, *, http_client: httpx.AsyncClient | None = None) -> "X402Middleware":
        facilitator_url = os.environ.get("BLOCKY402_FACILITATOR_URL")
        pay_to = os.environ.get("HEDERA_ACCOUNT_ID")
        missing = [
            name
            for name, value in (
                ("BLOCKY402_FACILITATOR_URL", facilitator_url),
                ("HEDERA_ACCOUNT_ID", pay_to),
            )
            if not value
        ]
        if missing:
            raise FacilitatorError(
                "Missing required env var(s) to run the x402-gated MCP "
                "server: " + ", ".join(missing) + " — see README.md > "
                "Environment Variables."
            )
        return cls(app, facilitator_url=facilitator_url, pay_to_account_id=pay_to, http_client=http_client)

    def _client(self) -> httpx.AsyncClient:
        return self._http_client or httpx.AsyncClient(timeout=10.0)

    async def _maybe_close(self, client: httpx.AsyncClient) -> None:
        if self._http_client is None:
            await client.aclose()

    async def _get_fee_payer(self) -> str:
        """`GET /supported` once and cache the facilitator's fee-payer account."""
        if self._fee_payer:
            return self._fee_payer
        client = self._client()
        try:
            response = await client.get(f"{self.facilitator_url}/supported")
        finally:
            await self._maybe_close(client)

        if response.status_code != 200:
            raise FacilitatorError(f"GET /supported returned HTTP {response.status_code}")
        body = response.json()

        # Real-world /supported responses (confirmed live against
        # api.testnet.blocky402.com) advertise a *different* fee payer per
        # CAIP-2 network family -- e.g. `signers` has separate `eip155:*`
        # (an 0x... EVM address), `solana:*`, and `hedera:*` entries, and
        # `kinds` has one object per (scheme, network) with its own
        # `extra.feePayer`. Blindly taking the first `signers` value grabs
        # whichever family happens to serialize first (an EVM address, in
        # practice), which the facilitator's own /verify then rejects with
        # "invalid_exact_hedera_payload_missing_fee_payer" since it isn't a
        # Hedera entity id -- so this must select by `self.network`
        # specifically, not just take anything non-empty.
        for kind in body.get("kinds", []):
            if kind.get("network") == self.network:
                fee_payer = (kind.get("extra") or {}).get("feePayer")
                if fee_payer:
                    self._fee_payer = fee_payer
                    return self._fee_payer

        signers = body.get("signers", {})
        network_family = self.network.split(":", 1)[0] + ":*"  # "hedera:testnet" -> "hedera:*"
        for key in (self.network, network_family):
            addrs = signers.get(key)
            if addrs:
                self._fee_payer = addrs[0]
                return self._fee_payer

        # Fallback for a simpler self-hosted facilitator that just exposes
        # `{"feePayer": ...}` with no per-network breakdown at all.
        fee_payer = body.get("feePayer")
        if fee_payer:
            self._fee_payer = fee_payer
            return self._fee_payer

        raise FacilitatorError(
            f"Could not determine a {self.network} fee payer from /supported: {body}"
        )

    def _requirements(self, tool_name: str, fee_payer: str) -> dict[str, Any]:
        """Build `PaymentRequirements` for `tool_name` per scheme_exact_hedera.md."""
        price = get_price(tool_name)
        return {
            "scheme": "exact",
            "network": self.network,
            "amount": str(price.price_tinybars()),
            "asset": HBAR_ASSET_ID,
            "payTo": self.pay_to_account_id,
            "maxTimeoutSeconds": 180,
            "extra": {"feePayer": fee_payer},
        }

    @staticmethod
    def _challenge(requirements: dict[str, Any], reason: str | None = None) -> JSONResponse:
        body = {
            "x402Version": X402_VERSION,
            "error": reason or "X-PAYMENT header is required",
            "accepts": [requirements],
        }
        return JSONResponse(body, status_code=402)

    @staticmethod
    def _decode_payment_header(raw: str) -> dict[str, Any]:
        try:
            decoded = base64.b64decode(raw)
            return json.loads(decoded)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 402
            raise FacilitatorError(f"Malformed {PAYMENT_HEADER} header: {exc}") from exc

    async def _verify_and_settle(
        self, payment_payload: dict[str, Any], requirements: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /verify then POST /settle, mirroring scaffold-hbar's server.ts."""
        client = self._client()
        try:
            verify_resp = await client.post(
                f"{self.facilitator_url}/verify",
                json={"paymentPayload": payment_payload, "paymentRequirements": requirements},
            )
            if verify_resp.status_code != 200:
                raise FacilitatorError(
                    f"POST /verify returned HTTP {verify_resp.status_code}: {verify_resp.text[:300]}"
                )
            verify_body = verify_resp.json()
            is_valid = verify_body.get("isValid", verify_body.get("is_valid"))
            if not is_valid:
                reason = (
                    verify_body.get("invalidReason")
                    or verify_body.get("invalid_reason")
                    or verify_body.get("invalidMessage")
                    or "payment invalid"
                )
                raise FacilitatorError(f"Payment verification failed: {reason}")

            settle_resp = await client.post(
                f"{self.facilitator_url}/settle",
                json={"paymentPayload": payment_payload, "paymentRequirements": requirements},
            )
            if settle_resp.status_code != 200:
                raise FacilitatorError(
                    f"POST /settle returned HTTP {settle_resp.status_code}: {settle_resp.text[:300]}"
                )
            settle_body = settle_resp.json()
            if not settle_body.get("success"):
                reason = (
                    settle_body.get("errorReason")
                    or settle_body.get("error_reason")
                    or settle_body.get("errorMessage")
                    or "settlement failed"
                )
                raise FacilitatorError(f"Payment settlement failed: {reason}")
            return settle_body
        finally:
            await self._maybe_close(client)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method != "POST":
            return await call_next(request)

        body_bytes = await request.body()
        try:
            rpc_body = json.loads(body_bytes) if body_bytes else {}
        except json.JSONDecodeError:
            return await call_next(request)

        if rpc_body.get("method") != "tools/call":
            return await call_next(request)

        params = rpc_body.get("params") or {}
        tool_name = params.get("name")
        try:
            get_price(tool_name)
        except UnknownToolError:
            # Not a priced (or not a known) tool — let the MCP app handle
            # it; it will error on an unknown tool name on its own.
            return await call_next(request)

        try:
            fee_payer = await self._get_fee_payer()
        except FacilitatorError as exc:
            logger.error("x402 middleware: facilitator unreachable: %s", exc)
            return JSONResponse(
                {"error": "facilitator_unavailable", "message": str(exc)}, status_code=503
            )

        requirements = self._requirements(tool_name, fee_payer)

        payment_header = request.headers.get(PAYMENT_HEADER)
        if not payment_header:
            return self._challenge(requirements)

        try:
            payment_payload = self._decode_payment_header(payment_header)
            settlement = await self._verify_and_settle(payment_payload, requirements)
        except FacilitatorError as exc:
            logger.info("x402 middleware: payment rejected for '%s': %s", tool_name, exc)
            return self._challenge(requirements, reason=str(exc))

        logger.info(
            "x402 middleware: settled payment for '%s' — tx %s",
            tool_name,
            settlement.get("transactionId") or settlement.get("transaction"),
        )

        response = await call_next(request)
        response.headers[SETTLEMENT_HEADER] = base64.b64encode(
            json.dumps(settlement).encode()
        ).decode()
        return response
