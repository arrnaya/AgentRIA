"""Tests for mcp_server/server.py — tool registration and app wiring.

No live network: verifies the 5 tools are registered with wire names that
exactly match mcp_server.pricing.TOOL_PRICES (the x402 middleware's price
lookup depends on this), and that build_app() wires X402Middleware in
given valid env config.
"""

from __future__ import annotations

import pytest

from mcp_server.pricing import TOOL_PRICES
from mcp_server.server import build_app, mcp
from mcp_server.x402_middleware import FacilitatorError, X402Middleware


def test_registered_tool_names_match_pricing_keys():
    registered = {t.name for t in mcp._tool_manager.list_tools()}
    assert registered == set(TOOL_PRICES)


def test_build_app_wires_x402_middleware(monkeypatch):
    monkeypatch.setenv("BLOCKY402_FACILITATOR_URL", "https://facilitator.test")
    monkeypatch.setenv("HEDERA_ACCOUNT_ID", "0.0.1234")
    app = build_app()
    middleware_classes = [m.cls for m in app.user_middleware]
    assert X402Middleware in middleware_classes


def test_build_app_fails_loud_without_config(monkeypatch):
    monkeypatch.delenv("BLOCKY402_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("HEDERA_ACCOUNT_ID", raising=False)
    with pytest.raises(FacilitatorError):
        build_app()
