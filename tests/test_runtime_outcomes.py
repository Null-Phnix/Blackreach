"""Offline regressions for browser origins, run outcomes, and checkpoints."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from blackreach.agent import Agent, AgentConfig, BrowserMode
from blackreach.exceptions import NavigationError, ProviderError
from blackreach.logging import SessionLogger, read_log, redact_log_text
from blackreach.memory import SessionMemory


@pytest.fixture
def agent(tmp_path, monkeypatch):
    # No provider initialization or live browser is needed for lifecycle tests.
    a = Agent.__new__(Agent)
    a.config = AgentConfig(max_steps=3, download_dir=tmp_path / "downloads")
    a.session_memory = SessionMemory()
    a.persistent_memory = MagicMock()
    a.session_id = 7
    a.hand = MagicMock()
    a.hand.get_url.return_value = "https://example.org/source"
    a._emit = MagicMock()
    a._logger = MagicMock()
    a._paused = False
    a._current_step = 0
    a._current_goal = "read source"
    a._step = MagicMock(return_value={"done": False})
    monkeypatch.setattr("blackreach.agent.time.sleep", lambda _: None)
    return a


def test_lightweight_uses_source_navigation(agent):
    agent._router = MagicMock()
    agent._router.plan_for.return_value = SimpleNamespace(mode=BrowserMode.LIGHTWEIGHT)
    with patch("blackreach.bulk_fetcher.BulkFetcher") as fetcher:
        fetcher.return_value.__enter__.return_value.fetch.return_value = SimpleNamespace(
            ok=True, html="<a href='/next'>next</a><script src='/app.js'></script>",
            extract_title=lambda: "Source", elapsed_ms=1,
        )
        assert agent._navigate_with_scan("https://example.org/source") is True
    agent.hand.goto.assert_called_once_with("https://example.org/source")
    agent.hand.page.set_content.assert_not_called()


@pytest.mark.parametrize("flags", [{"fatal": True}, {"recoverable": False}])
def test_permanent_error_wins_over_done(agent, flags):
    agent._step.return_value = {"done": True, "error": "cannot continue", **flags}
    result = agent._run_loop("read source", quiet=True)
    assert result["success"] is False
    assert result["status"] == "error"
    assert result["stop_reason"] == "permanent_error"
    assert result["error"] == "cannot continue"
    assert result["steps_taken"] == 1
    assert result["actions_taken"] == 0
    agent._step.assert_called_once()


def test_max_steps_counts_decisions_and_preserves_last_error(agent):
    agent._step.return_value = {"done": False, "error": "transient", "recoverable": True}
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "max_steps"
    assert result["stop_reason"] == "max_steps"
    assert result["steps_taken"] == 3
    assert result["actions_taken"] == 0
    assert result["error"] == "transient"


def test_done_counts_a_decision_but_no_action(agent):
    agent._step.return_value = {"done": True, "reason": "Read source", "result": "Summary"}
    result = agent._run_loop("read source", quiet=True)
    assert result["success"] is True
    assert result["status"] == "success"
    assert result["stop_reason"] == "goal_complete"
    assert result["result"] == "Summary"
    assert result["steps_taken"] == 1
    assert result["actions_taken"] == 0
    assert result["error"] is None
    agent._logger.session_end.assert_called_once()
    assert agent._logger.session_end.call_args.kwargs["stop_reason"] == "goal_complete"


def test_pause_before_decision_does_not_skip_it(agent):
    agent._paused = True
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "paused"
    assert result["paused"] is True
    assert result["steps_taken"] == 0
    assert agent.persistent_memory.save_session_state.call_args.kwargs["current_step"] == 0
    agent._step.assert_not_called()


def test_interrupt_saves_progress_and_reports_reason(agent):
    agent._step.side_effect = KeyboardInterrupt
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "interrupted"
    assert result["paused"] is True
    assert result["steps_taken"] == 1
    assert agent.persistent_memory.save_session_state.call_args.kwargs["status"] == "interrupted"
    agent.hand._release_all_keys.assert_called_once()
    agent._logger.session_end.assert_called_once()


def test_save_failure_is_error_without_claiming_paused(agent):
    agent._paused = True
    agent.persistent_memory.save_session_state.side_effect = OSError("disk full")
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "error"
    assert result["stop_reason"] == "state_save_failed"
    assert result["paused"] is False
    assert "disk full" in result["error"]
    agent._logger.session_end.assert_called_once()


def test_dead_browser_during_pause_still_saves_last_source(agent):
    agent._paused = True
    agent._recent_urls = ["https://example.org/last"]
    agent.hand.get_url.side_effect = OSError("closed")
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "paused"
    assert agent.persistent_memory.save_session_state.call_args.kwargs["current_url"] == "https://example.org/last"


def test_cleanup_failure_does_not_hide_session_end(agent):
    agent._step.return_value = {"done": True}
    agent.hand.sleep.side_effect = OSError("close failed")
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "error"
    assert result["success"] is False
    assert result["stop_reason"] == "cleanup_failed"
    agent._logger.session_end.assert_called_once()


def test_uncaught_step_exception_returns_terminal_error(agent):
    agent._step.side_effect = ProviderError("ollama", "offline provider")
    result = agent._run_loop("read source", quiet=True)
    assert result["status"] == "error"
    assert result["steps_taken"] == 1
    assert "offline provider" in result["error"]
    agent._logger.session_end.assert_called_once()


@pytest.mark.parametrize("url", ["about:blank", "data:text/html,<h1>source</h1>"])
def test_source_less_page_cannot_reach_model(agent, url):
    agent.check_browser_health = MagicMock(return_value=True)
    agent.hand.get_url.return_value = url
    agent.llm = MagicMock()
    result = Agent._step(agent, "read source", 1, quiet=True)
    assert result["done"] is False
    assert result["fatal"] is True
    assert result["recoverable"] is False
    agent.llm.generate.assert_not_called()


def test_pause_keeps_recorded_page_when_browser_is_blank(agent):
    agent.hand.get_url.return_value = "about:blank"
    agent._recent_urls = ["https://example.org/article", "data:text/html,injected"]
    assert agent.save_state() is True
    assert agent.persistent_memory.save_session_state.call_args.kwargs["current_url"] == "https://example.org/article"


def test_resume_blank_checkpoint_reopens_last_recorded_page(agent, monkeypatch):
    memory = SessionMemory(visited_urls=["https://example.org/start", "https://example.org/article"])
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 2,
        "session_memory": memory, "start_url": "https://example.org/start",
        "max_steps": 5, "current_url": "about:blank",
    }
    agent.ensure_browser = MagicMock(return_value=True)
    agent._step.return_value = {"done": True, "result": "Summary"}
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    agent.hand.goto.assert_called_once_with("https://example.org/article")
    assert result["status"] == "success"
    assert result["result"] == "Summary"


def test_resume_data_url_checkpoint_uses_start_url(agent, monkeypatch):
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 2,
        "session_memory": SessionMemory(visited_urls=["about:blank"]),
        "start_url": "https://example.org/start",
        "max_steps": 5, "current_url": "data:text/html,blank",
    }
    agent.ensure_browser = MagicMock(return_value=True)
    agent._step.return_value = {"done": True}
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    agent.hand.goto.assert_called_once_with("https://example.org/start")
    assert result["status"] == "success"


def test_resume_without_any_http_url_keeps_checkpoint(agent, monkeypatch):
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 2,
        "session_memory": SessionMemory(visited_urls=["about:blank", "data:text/html,blank"]),
        "start_url": "about:blank", "max_steps": 5, "current_url": "about:blank",
    }
    agent.ensure_browser = MagicMock(return_value=True)
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    assert result["status"] == "error"
    assert result["stop_reason"] == "navigation_failed"
    agent.hand.goto.assert_not_called()
    agent.persistent_memory.delete_session_state.assert_not_called()


def test_resume_clears_pause_and_retains_progress_on_navigation_failure(agent, monkeypatch):
    memory = SessionMemory(downloaded_files=["saved.pdf"], visited_urls=["https://example.org/source"])
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 2,
        "session_memory": memory, "start_url": "https://example.org/",
        "max_steps": 3, "current_url": "https://example.org/source",
    }
    agent._paused = True
    agent.ensure_browser = MagicMock(return_value=True)
    agent.hand.goto.side_effect = NavigationError("https://example.org/source", "offline")
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    assert agent._paused is False
    assert result["status"] == "error"
    assert result["stop_reason"] == "navigation_failed"
    assert result["downloads"] == ["saved.pdf"]
    assert result["steps_taken"] == 2
    agent.persistent_memory.delete_session_state.assert_not_called()
    agent._logger.session_end.assert_called_once()


def test_monotonic_actions_survive_history_truncation_and_serialization():
    memory = SessionMemory()
    for _ in range(250):
        memory.add_action({"action": "click"})
    assert len(memory.actions_taken) == 200
    restored = SessionMemory.from_dict(memory.to_dict())
    assert restored.action_count == 250
    assert restored.action_count_estimated is False


def test_legacy_snapshot_labels_estimated_action_count():
    restored = SessionMemory.from_dict({"actions_taken": [{"action": "click"}]})
    assert restored.action_count == 1
    assert restored.action_count_estimated is True


def test_session_end_retains_outcome_and_redacts_sensitive_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("blackreach.logging.LOG_DIR", tmp_path)
    logger = SessionLogger(8, "read source")
    logger.think(1, "private model reasoning")
    logger.act(1, "type", {"text": "secret entered text", "api_key": "secret-key"})
    logger.error("provider error", prompt="private prompt", response="private raw response")
    logger.session_end(False, 1, 0, 1, actions=1, status="error", stop_reason="permanent_error",
                       error="token=secret-token Bearer abcdef")
    raw = logger.log_file.read_text()
    for sensitive in ("private model reasoning", "secret entered text", "secret-key",
                      "private prompt", "private raw response", "secret-token", "abcdef"):
        assert sensitive not in raw
    end = read_log(logger.log_file)[-1]["data"]
    assert end["status"] == "error"
    assert end["stop_reason"] == "permanent_error"
    assert end["steps"] == 1
    assert end["actions"] == 1


def test_resume_budget_override_is_explicit(agent, monkeypatch):
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 3,
        "session_memory": SessionMemory(), "start_url": "https://example.org/",
        "max_steps": 3, "current_url": "https://example.org/source",
    }
    agent.ensure_browser = MagicMock(return_value=True)
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    exhausted = agent.resume(7, quiet=True)
    assert exhausted["status"] == "max_steps"
    assert exhausted["resumable"] is True
    agent._step.assert_not_called()
    agent.ensure_browser.assert_not_called()
    agent.hand.goto.assert_not_called()
    agent._step.return_value = {"done": True}
    resumed = agent.resume(7, quiet=True, max_steps=4)
    assert resumed["status"] == "success"
    assert resumed["steps_taken"] == 4
    agent._step.assert_called_once_with("read source", 4, quiet=True)


@pytest.mark.parametrize("failure", ["startup", "navigation", "initialization"])
def test_run_early_failure_finalizes_with_truthful_outcome(agent, monkeypatch, failure):
    session_logger = agent._logger
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: session_logger)
    agent.persistent_memory.get_stats.return_value = {"total_sessions": 0}
    agent.persistent_memory.start_session.return_value = 7
    agent.goal_engine = MagicMock()
    agent.goal_engine.decompose.return_value = SimpleNamespace(subtasks=[])
    agent.ensure_browser = MagicMock(return_value=failure != "startup")
    agent._navigate_with_scan = MagicMock()
    if failure == "navigation":
        agent._navigate_with_scan.side_effect = NavigationError("https://example.org/source", "offline")
    if failure == "initialization":
        agent.goal_engine.decompose.side_effect = OSError("initialization failed")
    result = agent.run("read source", quiet=True, start_url="https://example.org/source")
    assert result["status"] == "error"
    assert result["stop_reason"] == {
        "startup": "browser_start_failed", "navigation": "navigation_failed",
        "initialization": "initialization_failed",
    }[failure]
    assert result["steps_taken"] == 0
    assert result["actions_taken"] == 0
    assert result["failures"] == 1
    session_logger.session_end.assert_called_once()
    agent._step.assert_not_called()


def test_corrupt_checkpoint_returns_error_without_deleting_it(agent, monkeypatch):
    agent.persistent_memory.load_session_state.side_effect = ValueError("invalid checkpoint JSON")
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    assert result["status"] == "error"
    assert result["stop_reason"] == "state_load_failed"
    assert result["resumable"] is False
    agent.persistent_memory.end_session.assert_not_called()
    agent.persistent_memory.delete_session_state.assert_not_called()


@pytest.mark.parametrize("goal", ["find and summize soul eater anime", "summarize Soul Eater", "explain Soul Eater anime"])
def test_information_intent_searches_sources(agent, monkeypatch, goal):
    fallback = MagicMock(return_value=("https://search.example.org/?q=soul+eater", None))
    monkeypatch.setattr("blackreach.agent.get_search_fallback_url", fallback)
    knowledge = MagicMock()
    monkeypatch.setattr("blackreach.agent.reason_about_goal", knowledge)
    url, _, query = agent._get_smart_start_url(goal, quiet=True)
    assert url == "https://search.example.org/?q=soul+eater"
    assert query == goal
    knowledge.assert_not_called()


def test_terminal_log_write_failure_is_reported_safely(agent, tmp_path, monkeypatch):
    monkeypatch.setattr("blackreach.logging.LOG_DIR", tmp_path)
    agent._logger = SessionLogger(7, "read source")
    agent._step.return_value = {"done": True}
    with patch("builtins.open", side_effect=OSError("token=private-value disk full")):
        result = agent._run_loop("read source", quiet=True)
    assert result["success"] is False
    assert result["stop_reason"] == "log_write_failed"
    assert "private-value" not in result["error"]


def test_terminal_warning_and_quoted_credentials_are_redacted(agent, caplog):
    agent._step.return_value = {"done": True}
    agent._logger.session_end.side_effect = OSError('token=private-value')
    result = agent._run_loop("read source", quiet=True)
    assert "private-value" not in result["error"]
    assert "private-value" not in caplog.text
    assert "private-value" not in redact_log_text('{"api_key": "private-value"}')


def test_agent_contexts_bind_their_own_memory(tmp_path):
    with patch("blackreach.agent.LLM"):
        first = Agent(agent_config=AgentConfig(memory_db=tmp_path / "first.db", use_adaptive=False))
        second = Agent(agent_config=AgentConfig(memory_db=tmp_path / "second.db", use_adaptive=False))
    assert first.nav_context is not second.nav_context
    assert first.search_intel is not second.search_intel
    assert second.nav_context.persistent_memory is second.persistent_memory
    assert second.search_intel.persistent_memory is second.persistent_memory


def test_new_goal_resets_transient_failures_and_page_cache(agent, monkeypatch):
    session_logger = agent._logger
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: session_logger)
    agent.persistent_memory.get_stats.return_value = {"total_sessions": 0}
    agent.persistent_memory.start_session.return_value = 7
    agent.goal_engine = MagicMock()
    agent.goal_engine.decompose.return_value = SimpleNamespace(subtasks=[])
    agent.ensure_browser = MagicMock(return_value=False)
    agent._blocked_engines = {"old engine"}
    agent._failed_download_urls = {"old download"}
    agent._failed_urls = {"old source"}
    agent._clicked_selectors = {"old selector"}
    agent._page_cache = {"html": "old page"}
    agent._consecutive_failures = 5
    agent.run("new goal", quiet=True)
    assert agent._blocked_engines == set()
    assert agent._failed_download_urls == set()
    assert agent._failed_urls == set()
    assert agent._clicked_selectors == set()
    assert agent._consecutive_failures == 0
    assert all(value is None for value in agent._page_cache.values())


def test_terminal_save_failure_invalidates_older_checkpoint(agent):
    agent._current_step = 2
    agent._step.return_value = {"done": False, "error": "terminal", "fatal": True}
    agent.persistent_memory.save_session_state.side_effect = OSError("disk full")
    result = agent._run_loop("read source", start_step=3, quiet=True)
    assert result["status"] == "error"
    assert result["resumable"] is False
    agent.persistent_memory.delete_session_state.assert_called_once_with(7)


def test_exhausted_resume_retains_saved_url_without_browser(agent, monkeypatch):
    agent.hand = None
    agent.persistent_memory.load_session_state.return_value = {
        "session_id": 7, "goal": "read source", "current_step": 3,
        "session_memory": SessionMemory(), "start_url": "https://example.org/",
        "max_steps": 3, "current_url": "https://example.org/current-page",
    }
    agent.ensure_browser = MagicMock()
    monkeypatch.setattr("blackreach.agent.SessionLogger", lambda *a, **k: agent._logger)
    result = agent.resume(7, quiet=True)
    assert result["status"] == "max_steps"
    assert agent.persistent_memory.save_session_state.call_args.kwargs["current_url"] == "https://example.org/current-page"
    agent.ensure_browser.assert_not_called()
