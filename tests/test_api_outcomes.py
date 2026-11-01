"""Offline adapter contracts for run outcomes, configuration, and callbacks."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from blackreach.api import BlackreachAPI
from blackreach.config import Config
from blackreach.server import create_app


def test_api_preserves_returned_terminal_failure():
    api = BlackreachAPI()
    agent = MagicMock()
    api._get_agent = lambda: agent
    agent.run.return_value = {
        "success": False, "status": "error", "stop_reason": "permanent_error",
        "error": "fixture authentication failed", "steps_taken": 1,
        "actions_taken": 0, "resumable": False,
    }
    result = api.browse("fixture goal")
    assert result.errors == ["fixture authentication failed"]
    assert result.status == "error"
    assert result.stop_reason == "permanent_error"
    assert result.metadata["status"] == "error"


@pytest.mark.parametrize("status", ["max_steps", "paused", "interrupted"])
def test_api_preserves_non_success_checkpoint_outcomes(status):
    api = BlackreachAPI()
    agent = MagicMock()
    api._get_agent = lambda: agent
    agent.run.return_value = {
        "success": False, "status": status, "stop_reason": status,
        "steps_taken": 3, "actions_taken": 2, "resumable": True,
        "paused": status != "max_steps", "session_id": 7,
    }
    result = api.browse("fixture goal")
    assert result.status == status
    assert result.resumable is True
    assert result.actions_taken == 2
    assert result.errors == []


def test_api_restores_progress_callback_after_each_invocation():
    api = BlackreachAPI()
    agent = MagicMock()
    api._get_agent = lambda: agent
    original = MagicMock()
    agent.callbacks.on_step = original
    agent.run.return_value = {"success": True}
    progress = MagicMock()
    api.browse("first", on_progress=progress)
    assert agent.callbacks.on_step is original
    api.browse("second")
    assert agent.callbacks.on_step is original


def test_api_initialization_failure_is_returned_safely():
    api = BlackreachAPI()
    api._get_agent = MagicMock(side_effect=ValueError("api_key=synthetic-private"))
    result = api.browse("fixture goal")
    assert result.status == "error"
    assert result.errors and "synthetic-private" not in str(result.errors)


def test_api_uses_saved_provider_request_settings(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cfg = Config()
    cfg.default_provider = "openai"
    cfg.openai.default_model = "gpt-6-luna"
    cfg.openai.max_tokens = 8192
    cfg.openai.timeout_seconds = 15
    cfg.openai.base_url = "https://example.test/v1"
    with patch("blackreach.config.config_manager.load", return_value=cfg), patch("blackreach.config.config_manager.get_api_key", return_value="fixture-key"), patch("blackreach.agent.Agent") as agent_class:
        BlackreachAPI()._get_agent()
    llm = agent_class.call_args.kwargs["llm_config"]
    assert llm.provider == "openai"
    assert llm.model == "gpt-6-luna"
    assert llm.max_tokens == 8192
    assert llm.timeout_seconds == 15
    assert llm.api_base == "https://example.test/v1"


@pytest.mark.asyncio
async def test_rest_browse_forwards_error_and_outcome():
    api = MagicMock()
    agent = MagicMock()
    api._get_agent = lambda: agent
    agent.run.return_value = {"success": False, "status": "error", "stop_reason": "permanent_error", "error": "fixture provider error", "steps_taken": 1, "actions_taken": 0}
    real_api = BlackreachAPI()
    real_api._get_agent = lambda: agent
    with patch("blackreach.server.BlackreachAPI") as factory:
        factory.return_value.__enter__.return_value = real_api
        async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://127.0.0.1:7433") as client:
            response = await client.post("/v1/browse", json={"goal": "fixture"})
    data = response.json()["data"]
    assert data["errors"] == ["fixture provider error"]
    assert data["status"] == "error"
    assert data["stop_reason"] == "permanent_error"
    assert data["actions_taken"] == 0


def test_explicit_api_llm_config_wins_without_saved_config_access():
    from blackreach.api import ApiConfig
    from blackreach.llm import LLMConfig
    llm = LLMConfig(provider="openai", model="custom", api_key="fixture-key", max_tokens=2048)
    with patch("blackreach.config.config_manager.load") as load, patch("blackreach.agent.Agent") as agent_class:
        BlackreachAPI(ApiConfig(llm_config=llm))._get_agent()
    load.assert_not_called()
    assert agent_class.call_args.kwargs["llm_config"] is llm


@pytest.mark.parametrize("provider,expected_model", [("ollama", "deepseek-chat"), ("openai", "gpt-6-luna")])
def test_deepseek_shortcut_never_overrides_selected_cloud_provider(monkeypatch, provider, expected_model):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-deepseek-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    cfg = Config()
    cfg.default_provider = provider
    cfg.openai.default_model = "gpt-6-luna"
    with patch("blackreach.config.config_manager.load", return_value=cfg), patch("blackreach.config.config_manager.get_api_key", return_value="fixture-key"), patch("blackreach.agent.Agent") as agent_class:
        BlackreachAPI()._get_agent()
    llm = agent_class.call_args.kwargs["llm_config"]
    assert llm.model == expected_model
    if provider == "ollama":
        assert llm.api_mode == "chat"
        assert llm.api_base == "https://api.deepseek.com"


@pytest.mark.parametrize("status,expected_job", [("success", "done"), ("error", "failed"), ("max_steps", "done"), ("paused", "done"), ("interrupted", "done")])
def test_job_worker_forwards_outcome_and_distinguishes_failure(monkeypatch, tmp_path, status, expected_job):
    import importlib

    from blackreach.api import BrowseResult
    monkeypatch.setenv("BLACKREACH_JOB_STATE_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.delenv("BLACKREACH_API_KEY", raising=False)
    monkeypatch.delenv("BLACKREACH_API_KEY_FILE", raising=False)
    import mcp_server.blackreach_http_server as gateway
    gateway = importlib.reload(gateway)
    monkeypatch.setattr(gateway, "_persist_background_update_locked", lambda: None)
    gateway._jobs.clear()
    gateway._jobs["deadbeef"] = {"job_id": "deadbeef", "goal": "fixture"}
    queue = MagicMock()
    queue.get.side_effect = ["deadbeef", KeyboardInterrupt]
    monkeypatch.setattr(gateway, "_job_queue", queue)
    result = BrowseResult(
        success=status == "success", goal="fixture", status=status, stop_reason=status,
        errors=["fixture error"] if status == "error" else [],
        resumable=status != "success", actions_taken=2, steps_taken=3, session_id=7,
    )
    api = MagicMock()
    api.browse.return_value = result
    monkeypatch.setattr(gateway, "_make_api", lambda **kwargs: api)
    with pytest.raises(KeyboardInterrupt):
        gateway._worker_loop()
    job = gateway._jobs["deadbeef"]
    assert job["status"] == expected_job
    assert job["run_status"] == status
    assert job["stop_reason"] == status
    assert job["errors"] == result.errors
    assert job["resumable"] == result.resumable
    assert job["actions_taken"] == 2
    api.close.assert_called_once()
    queue.task_done.assert_called_once()


def load_mcp_adapter(monkeypatch):
    """Import the adapter with only its optional registration framework stubbed."""
    import importlib.util
    from pathlib import Path
    class FakeMCP:
        def __init__(self, *args):
            pass
        def tool(self, *args, **kwargs):
            return lambda fn: fn
    monkeypatch.setitem(__import__("sys").modules, "mcp.server.fastmcp", SimpleNamespace(FastMCP=FakeMCP))
    spec = importlib.util.spec_from_file_location("fixture_mcp_adapter", Path(__file__).parents[1] / "mcp_server" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status,job_status", [("max_steps", "done"), ("error", "failed")])
def test_mcp_poll_displays_job_and_run_outcome_without_claiming_goal_complete(monkeypatch, status, job_status):
    adapter = load_mcp_adapter(monkeypatch)
    response = MagicMock()
    response.json.return_value = {
        "status": job_status, "success": False, "run_status": status,
        "stop_reason": status, "steps_taken": 3, "actions_taken": 2,
        "resumable": True, "session_id": 7, "errors": ["fixture error"] if status == "error" else [],
        "created_at": 1, "finished_at": 2,
    }
    monkeypatch.setattr(adapter.httpx, "get", lambda *args, **kwargs: response)
    text = adapter._poll("deadbeef")
    assert f"Job status: {job_status}" in text
    assert f"Run status: {status}" in text
    assert f"Stop reason: {status}" in text
    assert "Actions taken: 2" in text
    assert "Resume with: blackreach run --resume 7" in text
    assert "Job finished" in text
    assert "Completed" not in text
    if status == "max_steps":
        assert "--steps 23" in text
    else:
        assert "fixture error" in text


def test_callback_restoration_also_runs_on_execution_failure():
    api = BlackreachAPI()
    agent = MagicMock()
    original = MagicMock()
    agent.callbacks.on_step = original
    agent.run.side_effect = RuntimeError("synthetic private request")
    api._get_agent = lambda: agent
    result = api.browse("fixture", on_progress=MagicMock())
    assert agent.callbacks.on_step is original
    assert result.status == "error"
    assert "synthetic private" not in str(result.errors)
    assert result.metadata["stop_reason"] == "permanent_error"


def test_api_deduplicates_already_reported_returned_error():
    api = BlackreachAPI()
    agent = MagicMock()
    api._get_agent = lambda: agent
    agent.run.return_value = {"success": False, "status": "error", "error": "fixture error", "errors": ["fixture error"]}
    assert api.browse("fixture").errors == ["fixture error"]
