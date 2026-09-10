import pytest

from mcp_server.pricing import TOOL_PRICES, UnknownToolError, get_price


def test_all_five_priced_tools_present():
    assert set(TOOL_PRICES) == {
        "get_gas_price",
        "get_sentiment",
        "get_risk_score",
        "get_price_feed",
        "stream_liquidation_alerts",
    }


@pytest.mark.parametrize(
    "tool_name,expected_hbar",
    [
        ("get_gas_price", 0.0005),
        ("get_sentiment", 0.001),
        ("get_risk_score", 0.002),
        ("get_price_feed", 0.0005),
        ("stream_liquidation_alerts", 0.001),
    ],
)
def test_prices_match_readme_table(tool_name, expected_hbar):
    assert TOOL_PRICES[tool_name].price_hbar == expected_hbar


def test_price_tinybars_conversion_exact():
    # 0.002 HBAR * 10**8 tinybars/HBAR = 200_000 tinybars
    assert get_price("get_risk_score").price_tinybars() == 200_000
    # 0.0005 HBAR * 10**8 = 50_000 tinybars
    assert get_price("get_gas_price").price_tinybars() == 50_000


def test_get_price_unknown_tool_raises():
    with pytest.raises(UnknownToolError, match="Unknown MCP tool"):
        get_price("not_a_real_tool")
