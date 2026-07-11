"""REST wrapper tests for forwarding caller-controlled options."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from blackreach.api import BrowseResult, SearchResult
from blackreach.server import create_app


def test_async_gateway_requires_configured_api_key(monkeypatch):
    """The deployed Flask gateway authenticates data-bearing routes."""
    import importlib
    import mcp_server.blackreach_http_server as gateway

    monkeypatch.setenv("BLACKREACH_API_KEY", "gateway-secret")
    gateway = importlib.reload(gateway)
    client = gateway.app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/jobs").status_code == 401
    assert client.get(
        "/jobs", headers={"Authorization": "Bearer gateway-secret"}
    ).status_code == 200

    monkeypatch.delenv("BLACKREACH_API_KEY", raising=False)
    importlib.reload(gateway)


@pytest.mark.asyncio
async def test_browse_endpoint_forwards_start_url_and_runtime_config(monkeypatch):
    seen = {}

    class FakeAPI:
        def __init__(self, config):
            seen["config"] = config

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def browse(self, goal, start_url=None):
            seen["goal"] = goal
            seen["start_url"] = start_url
            return BrowseResult(success=True, goal=goal, result="done")

    monkeypatch.setattr("blackreach.server.BlackreachAPI", FakeAPI)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/browse", json={
            "goal": "Inspect this page",
            "start_url": "https://example.com/start",
            "max_steps": 17,
            "headless": True,
            "verbose": True,
        })

    assert response.status_code == 200
    assert seen["start_url"] == "https://example.com/start"
    assert seen["config"].max_steps == 17
    assert seen["config"].headless is True
    assert seen["config"].verbose is True


@pytest.mark.asyncio
async def test_search_endpoint_forwards_num_results(monkeypatch):
    search = MagicMock(return_value=SearchResult(
        query="test", results=[], source="huginn-starsearch", total_found=0
    ))
    monkeypatch.setattr("blackreach.server.search", search)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/search", json={"query": "test", "num_results": 23}
        )

    assert response.status_code == 200
    search.assert_called_once_with("test", max_results=23)
