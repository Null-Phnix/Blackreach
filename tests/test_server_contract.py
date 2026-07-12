"""REST wrapper tests for forwarding caller-controlled options."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from blackreach.api import BrowseResult, SearchResult
from blackreach.server import create_app


def test_async_gateway_requires_configured_api_key(monkeypatch, tmp_path):
    """The deployed Flask gateway authenticates data-bearing routes."""
    import importlib

    monkeypatch.setenv("BLACKREACH_API_KEY", "gateway-secret")
    monkeypatch.setenv("BLACKREACH_JOB_STATE_FILE", str(tmp_path / "jobs.json"))
    import mcp_server.blackreach_http_server as gateway
    gateway = importlib.reload(gateway)
    client = gateway.app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/jobs").status_code == 401
    assert client.get(
        "/jobs", headers={"Authorization": "Bearer gateway-secret"}
    ).status_code == 200

    monkeypatch.delenv("BLACKREACH_API_KEY", raising=False)
    importlib.reload(gateway)


def test_async_gateway_persists_results_and_recovers_interrupted_jobs(monkeypatch, tmp_path):
    """Restarts retain terminal jobs and make interrupted work explicitly fail."""
    import importlib
    import json
    import stat

    state_file = tmp_path / "state" / "jobs.json"
    monkeypatch.setenv("BLACKREACH_JOB_STATE_FILE", str(state_file))
    monkeypatch.delenv("BLACKREACH_API_KEY", raising=False)

    import mcp_server.blackreach_http_server as gateway
    gateway = importlib.reload(gateway)
    monkeypatch.setattr(gateway, "_start_worker", lambda: None)

    completed_id = gateway._submit_job(
        "Inspect the explicit page",
        start_url="https://example.com/start",
        max_steps=7,
    )
    interrupted_id = gateway._submit_job("This run will be interrupted")
    with gateway._jobs_lock:
        gateway._jobs[completed_id].update({
            "status": gateway.JobStatus.DONE,
            "finished_at": 123.0,
            "success": True,
            "result": "Example Domain",
        })
        gateway._jobs[interrupted_id]["status"] = gateway.JobStatus.RUNNING
        gateway._persist_jobs_locked()

    on_disk = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(on_disk["jobs"]) == 2
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600

    gateway = importlib.reload(gateway)
    assert gateway._jobs[completed_id]["status"] == gateway.JobStatus.DONE
    assert gateway._jobs[completed_id]["start_url"] == "https://example.com/start"
    assert gateway._jobs[completed_id]["result"] == "Example Domain"
    assert gateway._jobs[interrupted_id]["status"] == gateway.JobStatus.FAILED
    assert gateway._jobs[interrupted_id]["error_code"] == "service_restarted"
    assert gateway.app.test_client().get("/health").json["job_store"] == "ok"


def test_async_gateway_fails_closed_on_corrupt_job_journal(monkeypatch, tmp_path):
    """A corrupt journal is reported and never overwritten by a new job."""
    import importlib

    state_file = tmp_path / "jobs.json"
    state_file.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("BLACKREACH_JOB_STATE_FILE", str(state_file))
    monkeypatch.delenv("BLACKREACH_API_KEY", raising=False)

    import mcp_server.blackreach_http_server as gateway
    gateway = importlib.reload(gateway)
    client = gateway.app.test_client()

    assert client.get("/health").json["job_store"] == "degraded"
    response = client.post("/browse", json={"goal": "must not enqueue"})
    assert response.status_code == 503
    assert response.json["code"] == "job_store_unavailable"
    assert state_file.read_text(encoding="utf-8") == "{not-json"


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
