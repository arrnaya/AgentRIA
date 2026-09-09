import httpx
import pytest
import respx

from graph.subgraph_client import SUBGRAPH_IDS, SubgraphClient, SubgraphQueryError

API_KEY = "test-key"


def _endpoint(subgraph_key: str) -> str:
    return f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_IDS[subgraph_key]}"


@respx.mock
async def test_query_returns_data_on_success():
    route = respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json={"data": {"liquidityPools": []}})
    )
    client = SubgraphClient(api_key=API_KEY)

    result = await client.query("uniswap-v3-ethereum", "query { liquidityPools { id } }")

    assert route.called
    assert result == {"liquidityPools": []}


@respx.mock
async def test_query_raises_on_http_error():
    respx.post(_endpoint("aave-v3-ethereum")).mock(return_value=httpx.Response(500, text="boom"))
    client = SubgraphClient(api_key=API_KEY)

    with pytest.raises(SubgraphQueryError, match="HTTP 500"):
        await client.query("aave-v3-ethereum", "query { markets { id } }")


@respx.mock
async def test_query_raises_on_graphql_error():
    respx.post(_endpoint("uniswap-v3-ethereum")).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "bad field"}]})
    )
    client = SubgraphClient(api_key=API_KEY)

    with pytest.raises(SubgraphQueryError, match="GraphQL error"):
        await client.query("uniswap-v3-ethereum", "query { nope }")


async def test_unknown_subgraph_key_raises():
    client = SubgraphClient(api_key=API_KEY)
    with pytest.raises(SubgraphQueryError, match="Unknown subgraph"):
        await client.query("not-a-real-subgraph", "query {}")


def test_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("GRAPH_API_KEY", raising=False)
    with pytest.raises(SubgraphQueryError, match="GRAPH_API_KEY"):
        SubgraphClient.from_env()


def test_from_env_reads_api_key(monkeypatch):
    monkeypatch.setenv("GRAPH_API_KEY", "abc123")
    client = SubgraphClient.from_env()
    assert client.api_key == "abc123"
