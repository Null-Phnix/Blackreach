# Regression tests for action-tracking and goal-negation bugs (2026-05-08)
import pytest
from unittest.mock import MagicMock, patch
from blackreach.agent import Agent, AgentConfig, goal_needs_download
from blackreach.llm import LLMConfig
from blackreach.exceptions import BrowserError


class TestStepRecordsOnFailure:
    """Every ReAct step—success or failure—must be recorded in session_memory."""

    @pytest.fixture
    def agent(self, tmp_path):
        agent = Agent(
            llm_config=LLMConfig(provider="ollama", model="qwen2.5:14b"),
            agent_config=AgentConfig(max_steps=3, memory_db=tmp_path / "test.db")
        )
        agent.hand = MagicMock()
        agent.hand.get_url.return_value = "https://example.com"
        agent.hand.get_html.return_value = "<html><body><a data-br-id='1'>hi</a></body></html>"
        agent.hand.get_title.return_value = "Example"
        agent.detector = MagicMock()
        agent.detector.detect_challenge.return_value = MagicMock(detected=False)
        agent.stuck_detector = MagicMock()
        agent.stuck_detector.check.return_value = MagicMock(is_stuck=False)
        agent.error_recovery = MagicMock()
        agent.error_recovery.handle.return_value = MagicMock(
            wait_seconds=0, should_skip=False, new_context={}
        )
        agent.error_recovery.categorize.return_value = MagicMock(
            category=MagicMock(value="browser"), recoverable=True
        )
        return agent

    def test_step_failure_records_action(self, agent):
        """When _execute_action raises, session_memory still tracks the step."""
        agent.llm.generate = MagicMock(return_value='{"thought":"click","action":"click","element":1}')
        agent._execute_action = MagicMock(side_effect=BrowserError("element not found"))

        result = agent._step("test goal", step_num=1, quiet=True)

        assert result["done"] is False
        assert result["error"] == "element not found"
        assert len(agent.session_memory.actions_taken) == 1
        assert agent.session_memory.actions_taken[0]["action"] == "click"
        assert agent.session_memory.actions_taken[0]["success"] is False
        assert agent.session_memory.actions_taken[0]["error"] == "element not found"
        assert len(agent._action_history) == 1
        assert "ERROR" in agent._action_history[0]

    def test_step_success_records_action(self, agent):
        """Happy path also records properly."""
        agent.llm.generate = MagicMock(return_value='{"thought":"click","action":"click","element":1}')
        agent._execute_action = MagicMock(return_value={"action": "click", "element": 1})

        result = agent._step("test goal", step_num=1, quiet=True)

        assert not result.get("done")
        assert "error" not in result
        assert len(agent.session_memory.actions_taken) == 1
        assert agent.session_memory.actions_taken[0]["success"] is True

    def test_done_without_files_is_blocked_for_notes(self, agent):
        agent.llm.generate = MagicMock(
            return_value='{"thought":"nothing here","action":"done","args":{"reason":"complete"}}'
        )
        result = agent._step("download the lecture notes", step_num=1, quiet=True)
        assert result["done"] is False
        assert result.get("blocked") is True

    def test_done_is_allowed_when_goal_forbids_downloads(self, agent):
        agent.llm.generate = MagicMock(
            return_value='{"thought":"done","action":"done","args":{"reason":"complete"}}'
        )
        result = agent._step(
            "find info on the hantavirus, don't download anything",
            step_num=1,
            quiet=True,
        )
        assert result.get("done") is True


class TestDownloadUrlDoesNotAbortRun:
    """A failed download whose URL merely contains 'resources' or '401' must not end the run."""

    def test_resources_404_is_not_fatal(self, tmp_path):
        from blackreach.exceptions import DownloadError

        agent = Agent(
            llm_config=LLMConfig(provider="ollama", model="qwen2.5:14b"),
            agent_config=AgentConfig(max_steps=3, memory_db=tmp_path / "test.db"),
        )
        agent.hand = MagicMock()
        agent.hand.get_url.return_value = "https://example.com/resources"
        agent.hand.get_html.return_value = "<html><body><a data-br-id='1'>hi</a></body></html>"
        agent.hand.get_title.return_value = "Example"
        agent.detector = MagicMock()
        agent.detector.detect_challenge.return_value = MagicMock(detected=False)
        agent.stuck_detector = MagicMock()
        agent.stuck_detector.check.return_value = MagicMock(is_stuck=False)
        agent.llm.generate = MagicMock(
            return_value='{"thought":"download the report","action":"download","args":{"url":"https://example.com/resources/report.pdf"}}'
        )
        agent._execute_action = MagicMock(side_effect=DownloadError(
            "https://example.com/resources/report.pdf", reason="Not Found", status_code=404,
        ))

        result = agent._step("download the annual report", step_num=1, quiet=True)

        assert result["done"] is False
        assert result.get("fatal") is not True
        assert result.get("recoverable") is not False


class TestGoalNegationNotDownload:
    """Goals like 'don't download anything' must NOT be blocked as download tasks."""

    def test_dont_download_is_not_download(self):
        assert goal_needs_download("find info on the hantavirus, don't download anything") is False

    def test_never_save_is_not_download(self):
        assert goal_needs_download("never save this file") is False

    def test_plain_download_is_download(self):
        assert goal_needs_download("download cat pictures") is True

    def test_list_download_counts_not_blocked(self):
        assert goal_needs_download("list most downloaded programs") is False

    def test_notes_and_another_are_still_downloads(self):
        """Substring 'not' must not cancel a real file request."""
        assert goal_needs_download("download the lecture notes") is True
        assert goal_needs_download("save another pdf") is True
        assert goal_needs_download("download file no. 3") is True

    def test_find_and_download_still_requires_a_file(self):
        assert goal_needs_download("find and download the annual report pdf") is True

    def test_download_statistics_stay_informational(self):
        assert goal_needs_download("what is the download count") is False


class TestRunLoopErrorDisplay:
    """_run_loop() must log per-step errors instead of silently ignoring them."""

    @pytest.fixture
    def agent(self, tmp_path):
        agent = Agent(
            llm_config=LLMConfig(provider="ollama", model="qwen2.5:14b"),
            agent_config=AgentConfig(max_steps=3, memory_db=tmp_path / "test.db")
        )
        agent.hand = None
        agent.persistent_memory = MagicMock()
        agent._current_goal = "test"
        return agent

    @patch("blackreach.agent.time.sleep")
    def test_error_display_accumulates(self, mock_sleep, agent, capsys):
        """Non-recoverable repeated errors should eventually break the loop."""
        def mock_step(goal, step_num, quiet=False):
            agent.session_memory.add_action(
                {"action": "click", "args": {}, "thought": "t", "success": False, "error": "browser timeout"}
            )
            return {"done": False, "error": "browser timeout", "recoverable": False}
        agent._step = mock_step
        result = agent._run_loop("test goal", start_step=1, quiet=True)

        # Loop should break after first unrecoverable error
        assert result["success"] is False
        assert result["steps_taken"] == 1

    @patch("blackreach.agent.time.sleep")
    def test_recoverable_errors_keep_loop(self, mock_sleep, agent):
        """Recoverable errors let the loop continue."""
        def mock_step(goal, step_num, quiet=False):
            agent.session_memory.add_action(
                {"action": "click", "args": {}, "thought": "t", "success": False, "error": "transient"}
            )
            return {"done": False, "error": "transient", "recoverable": True}
        agent._step = mock_step
        result = agent._run_loop("test goal", start_step=1, quiet=True)
        # After max_steps it exhausts
        assert result["steps_taken"] == agent.config.max_steps
