"""Regressions from a real public-documentation comparison run.

The browser and model are replaced here; the agent's action bookkeeping and
goal planner run unchanged. No network, credentials, or live sites are used.
"""
import json
from unittest.mock import MagicMock

import pytest

from blackreach.agent import Agent, AgentConfig
from blackreach.exceptions import BrowserError
from blackreach.goal_engine import GoalEngine, GoalType
from blackreach.llm import LLMConfig


@pytest.fixture
def agent(tmp_path, monkeypatch):
    a = Agent(
        llm_config=LLMConfig(provider="ollama", model="test"),
        agent_config=AgentConfig(max_steps=8, memory_db=tmp_path / "test.db"),
    )
    a.hand = MagicMock()
    a.hand.get_url.return_value = "https://example.org/source"
    a.hand.get_html.return_value = "<html><body><a data-br-id='1'>next</a></body></html>"
    a.hand.get_title.return_value = "Source"
    a.detector = MagicMock()
    a.detector.detect_challenge.return_value = MagicMock(detected=False)
    a.stuck_detector = MagicMock()
    a.stuck_detector.check.return_value = MagicMock(is_stuck=False)
    a.error_recovery = MagicMock()
    a.error_recovery.handle.return_value = MagicMock(wait_seconds=0, should_skip=False, new_context={})
    a.error_recovery.categorize.return_value = MagicMock(
        category=MagicMock(value="browser"), recoverable=True,
    )
    # Exercise failure accounting independently of the URL revisit heuristic.
    a._get_stuck_hint = MagicMock(return_value="")
    monkeypatch.setattr("blackreach.agent.time.sleep", lambda _: None)
    yield a
    a.persistent_memory.close()


def run_actions(agent, targets, outcomes):
    agent.llm.generate = MagicMock(side_effect=[
        json.dumps({"action": "navigate", "args": {"url": target}})
        for target in targets
    ])
    agent._execute_action = MagicMock(side_effect=outcomes)
    for step in range(1, len(targets) + 1):
        agent._step("Compare public documentation", step_num=step, quiet=True)


@pytest.mark.parametrize("same_target", [False, True])
def test_successful_navigation_does_not_invent_failure(agent, same_target):
    targets = ["https://example.org/a" if same_target else f"https://example.org/{i}" for i in range(3)]
    run_actions(agent, targets, [{"url": target} for target in targets])
    assert agent.session_memory.failures == []
    assert agent._repeated_failure_count == 0
    assert agent._last_failed_action is None


def test_failures_at_different_targets_are_not_one_repeated_failure(agent):
    targets = [f"https://example.org/{i}" for i in range(3)]
    run_actions(agent, targets, [BrowserError("offline") for _ in targets])
    assert len(agent.session_memory.failures) == 3
    assert not any("failed 3 times" in failure for failure in agent.session_memory.failures)


def test_success_breaks_a_repeated_failure_streak(agent):
    targets = ["https://example.org/next"] * 4
    run_actions(agent, targets, [BrowserError("offline"), BrowserError("offline"),
                                {"url": targets[0]}, BrowserError("offline")])
    assert len(agent.session_memory.failures) == 3
    assert agent._repeated_failure_count == 1


@pytest.mark.parametrize("raises", [True, False])
def test_actual_repeated_failure_still_warns(agent, raises):
    outcomes = [BrowserError("offline") if raises else {"error": "offline"} for _ in range(3)]
    run_actions(agent, ["https://example.org/next"] * 3, outcomes)
    assert any("failed 3 times" in failure for failure in agent.session_memory.failures)


@pytest.mark.parametrize("goal", [
    "Visit the documentation. Do not log in, submit forms, or download files.",
    "Visit the documentation; don't download anything.",
    "Visit the documentation without saving files.",
    "Visit the documentation. Never fetch files.",
    "Visit the documentation. Don’t download anything.",
])
def test_forbidden_download_is_not_a_planned_download(goal):
    plan = GoalEngine().decompose(goal)
    assert plan.goal_type == GoalType.NAVIGATE
    assert plan.target_downloads == 0
    assert not any(task.task_type == GoalType.DOWNLOAD for task in plan.subtasks)


@pytest.mark.parametrize("goal", [
    "Download the lecture notes.",
    "Save another PDF.",
    "Find and download the annual report. Do not log in.",
    "Don't download the images. Download the report.",
    "Don't download the images, but download the report.",
])
def test_positive_download_request_is_preserved(goal):
    assert GoalEngine().detect_goal_type(goal) == GoalType.DOWNLOAD
