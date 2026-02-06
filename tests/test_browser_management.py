"""
Unit tests for browser management features (EPIC 1 fixes).

Tests the new browser lifecycle management methods:
- is_awake property
- is_healthy() method
- ensure_awake() method
- restart() method
- Agent.ensure_browser()
- Agent.restart_browser()
- Agent.check_browser_health()
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from playwright.sync_api import Error as PlaywrightError
from blackreach.browser import Hand
from blackreach.agent import Agent, AgentConfig
from blackreach.stealth import StealthConfig
from blackreach.resilience import RetryConfig
from blackreach.exceptions import BrowserNotReadyError, BrowserError, NavigationError


# =============================================================================
# Hand Browser Management Tests
# =============================================================================

class TestHandIsAwake:
    """Tests for Hand.is_awake property."""

    def test_is_awake_false_initially(self):
        """is_awake returns False before wake() is called."""
        hand = Hand()
        assert hand.is_awake is False

    def test_is_awake_false_when_playwright_none(self):
        """is_awake returns False when playwright is None."""
        hand = Hand()
        hand._playwright = None
        hand._browser = Mock()
        hand._page = Mock()
        assert hand.is_awake is False

    def test_is_awake_false_when_browser_none(self):
        """is_awake returns False when browser is None."""
        hand = Hand()
        hand._playwright = Mock()
        hand._browser = None
        hand._page = Mock()
        assert hand.is_awake is False

    def test_is_awake_false_when_page_none(self):
        """is_awake returns False when page is None."""
        hand = Hand()
        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = None
        assert hand.is_awake is False

    def test_is_awake_true_when_all_set(self):
        """is_awake returns True when playwright, browser, and page are set."""
        hand = Hand()
        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = Mock()
        assert hand.is_awake is True


class TestHandIsHealthy:
    """Tests for Hand.is_healthy() method."""

    def test_is_healthy_false_when_not_awake(self):
        """is_healthy returns False when browser is not awake."""
        hand = Hand()
        assert hand.is_healthy() is False

    def test_is_healthy_true_when_page_responsive(self):
        """is_healthy returns True when page responds to basic operations."""
        hand = Hand()
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Example"

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        assert hand.is_healthy() is True

    def test_is_healthy_false_when_page_throws(self):
        """is_healthy returns False when page operations throw."""
        hand = Hand()
        mock_page = Mock()

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        # Use a property that throws PlaywrightError
        type(mock_page).url = PropertyMock(side_effect=PlaywrightError("Page closed"))

        assert hand.is_healthy() is False

    def test_is_healthy_resets_error_counter_on_success(self):
        """is_healthy resets consecutive error counter on success."""
        hand = Hand()
        hand._consecutive_errors = 5

        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Test"

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        hand.is_healthy()

        assert hand._consecutive_errors == 0

    def test_is_healthy_increments_error_counter_on_failure(self):
        """is_healthy increments consecutive error counter on failure."""
        hand = Hand()
        hand._consecutive_errors = 0

        mock_page = Mock()
        type(mock_page).url = PropertyMock(side_effect=PlaywrightError("Error"))

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        hand.is_healthy()

        assert hand._consecutive_errors == 1


class TestHandEnsureAwake:
    """Tests for Hand.ensure_awake() method."""

    def test_ensure_awake_returns_true_when_already_healthy(self):
        """ensure_awake returns True when browser is already awake and healthy."""
        hand = Hand()
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Test"

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        assert hand.ensure_awake() is True

    def test_ensure_awake_calls_wake_when_not_awake(self):
        """ensure_awake calls wake() when browser is not awake."""
        hand = Hand()

        with patch.object(hand, 'wake') as mock_wake:
            hand.ensure_awake()
            mock_wake.assert_called_once()

    def test_ensure_awake_calls_sleep_before_restart(self):
        """ensure_awake calls sleep() before restarting unhealthy browser."""
        hand = Hand()

        # Make browser appear awake but unhealthy
        hand._playwright = Mock()
        hand._browser = Mock()
        mock_page = Mock()
        type(mock_page).url = PropertyMock(side_effect=PlaywrightError("Unhealthy"))
        hand._page = mock_page

        with patch.object(hand, 'sleep') as mock_sleep, \
             patch.object(hand, 'wake') as mock_wake:
            hand.ensure_awake()
            mock_sleep.assert_called()
            mock_wake.assert_called()

    def test_ensure_awake_returns_false_when_wake_fails(self):
        """ensure_awake returns False when wake() raises exception."""
        hand = Hand()

        with patch.object(hand, 'wake', side_effect=Exception("Wake failed")):
            assert hand.ensure_awake() is False


class TestHandRestart:
    """Tests for Hand.restart() method."""

    def test_restart_calls_sleep_and_wake(self):
        """restart() calls sleep() then wake()."""
        hand = Hand()

        with patch.object(hand, 'sleep') as mock_sleep, \
             patch.object(hand, 'wake') as mock_wake:
            hand.restart()
            mock_sleep.assert_called()
            mock_wake.assert_called()

    def test_restart_returns_true_on_success(self):
        """restart() returns True when successful."""
        hand = Hand()

        with patch.object(hand, 'sleep'), \
             patch.object(hand, 'wake'):
            assert hand.restart() is True

    def test_restart_returns_false_when_wake_fails(self):
        """restart() returns False when wake() fails."""
        hand = Hand()

        with patch.object(hand, 'sleep'), \
             patch.object(hand, 'wake', side_effect=Exception("Wake failed")):
            assert hand.restart() is False

    def test_restart_saves_and_restores_url(self):
        """restart() tries to navigate back to current URL."""
        hand = Hand()

        # Set up initial state with a URL
        mock_page = Mock()
        mock_page.url = "https://example.com/page"
        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        with patch.object(hand, 'sleep'), \
             patch.object(hand, 'wake'), \
             patch.object(hand, 'goto') as mock_goto:
            hand.restart()
            mock_goto.assert_called_once()
            args, kwargs = mock_goto.call_args
            assert "example.com" in args[0]

    def test_restart_handles_sleep_errors_gracefully(self):
        """restart() continues even if sleep() raises."""
        hand = Hand()

        with patch.object(hand, 'sleep', side_effect=Exception("Sleep error")), \
             patch.object(hand, 'wake'):
            # Should not raise
            result = hand.restart()
            assert result is True

    def test_restart_handles_navigation_errors_gracefully(self):
        """restart() returns True even if navigation fails."""
        hand = Hand()

        mock_page = Mock()
        mock_page.url = "https://example.com"
        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        with patch.object(hand, 'sleep'), \
             patch.object(hand, 'wake'), \
             patch.object(hand, 'goto', side_effect=Exception("Nav failed")):
            result = hand.restart()
            assert result is True


class TestHandWakeCount:
    """Tests for wake count tracking."""

    def test_wake_count_starts_at_zero(self):
        """_wake_count starts at 0."""
        hand = Hand()
        assert hand._wake_count == 0

    def test_consecutive_errors_starts_at_zero(self):
        """_consecutive_errors starts at 0."""
        hand = Hand()
        assert hand._consecutive_errors == 0


# =============================================================================
# Agent Browser Management Tests
# =============================================================================

class TestAgentCreateBrowser:
    """Tests for Agent._create_browser() method."""

    def test_create_browser_returns_hand(self, tmp_path):
        """_create_browser returns a Hand instance."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        hand = agent._create_browser()

        assert isinstance(hand, Hand)

    def test_create_browser_uses_config_headless(self, tmp_path):
        """_create_browser uses headless setting from config."""
        config = AgentConfig(memory_db=tmp_path / "test.db", headless=True)
        agent = Agent(agent_config=config)

        hand = agent._create_browser()

        assert hand.headless is True

    def test_create_browser_uses_config_download_dir(self, tmp_path):
        """_create_browser uses download_dir from config."""
        download_path = tmp_path / "downloads"
        config = AgentConfig(memory_db=tmp_path / "test.db", download_dir=download_path)
        agent = Agent(agent_config=config)

        hand = agent._create_browser()

        assert hand.download_dir == download_path

    def test_create_browser_uses_config_browser_type(self, tmp_path):
        """_create_browser uses browser_type from config."""
        config = AgentConfig(memory_db=tmp_path / "test.db", browser_type="firefox")
        agent = Agent(agent_config=config)

        hand = agent._create_browser()

        assert hand.browser_type == "firefox"


class TestAgentEnsureBrowser:
    """Tests for Agent.ensure_browser() method."""

    def test_ensure_browser_creates_hand_if_none(self, tmp_path):
        """ensure_browser creates Hand if self.hand is None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.hand is None

        with patch.object(Hand, 'ensure_awake', return_value=True):
            result = agent.ensure_browser()

        assert agent.hand is not None
        assert result is True

    def test_ensure_browser_uses_existing_hand(self, tmp_path):
        """ensure_browser uses existing Hand instance."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        existing_hand = Hand()
        agent.hand = existing_hand

        with patch.object(existing_hand, 'ensure_awake', return_value=True):
            agent.ensure_browser()

        assert agent.hand is existing_hand

    def test_ensure_browser_returns_ensure_awake_result(self, tmp_path):
        """ensure_browser returns result of Hand.ensure_awake()."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(Hand, 'ensure_awake', return_value=False):
            result = agent.ensure_browser()

        assert result is False

    def test_ensure_browser_idempotent(self, tmp_path):
        """ensure_browser is safe to call multiple times."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(Hand, 'ensure_awake', return_value=True):
            result1 = agent.ensure_browser()
            first_hand = agent.hand
            result2 = agent.ensure_browser()
            second_hand = agent.hand

        assert result1 is True
        assert result2 is True
        assert first_hand is second_hand


class TestAgentRestartBrowser:
    """Tests for Agent.restart_browser() method."""

    def test_restart_browser_creates_hand_if_none(self, tmp_path):
        """restart_browser creates Hand if self.hand is None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.hand is None

        with patch.object(Hand, 'restart', return_value=True):
            agent.restart_browser()

        assert agent.hand is not None

    def test_restart_browser_returns_restart_result(self, tmp_path):
        """restart_browser returns result of Hand.restart()."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(Hand, 'restart', return_value=False):
            result = agent.restart_browser()

        assert result is False

    def test_restart_browser_navigates_to_url(self, tmp_path):
        """restart_browser navigates to provided URL after restart."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.restart.return_value = True
        agent.hand = mock_hand

        agent.restart_browser(navigate_to="https://example.com")

        mock_hand.goto.assert_called_once_with("https://example.com")

    def test_restart_browser_no_navigation_without_url(self, tmp_path):
        """restart_browser doesn't navigate if no URL provided."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.restart.return_value = True
        agent.hand = mock_hand

        agent.restart_browser()

        mock_hand.goto.assert_not_called()

    def test_restart_browser_handles_navigation_error(self, tmp_path):
        """restart_browser handles navigation errors gracefully."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.restart.return_value = True
        mock_hand.goto.side_effect = NavigationError("Nav error")
        agent.hand = mock_hand

        # Should not raise
        result = agent.restart_browser(navigate_to="https://example.com")

        assert result is True


class TestAgentCheckBrowserHealth:
    """Tests for Agent.check_browser_health() method."""

    def test_check_browser_health_false_when_no_hand(self, tmp_path):
        """check_browser_health returns False when hand is None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.hand is None
        assert agent.check_browser_health() is False

    def test_check_browser_health_delegates_to_hand(self, tmp_path):
        """check_browser_health delegates to Hand.is_healthy()."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        result = agent.check_browser_health()

        assert result is True
        mock_hand.is_healthy.assert_called_once()


class TestAgentGetDomainWithBrowserCheck:
    """Tests for Agent._get_domain() with browser health awareness."""

    def test_get_domain_handles_unhealthy_browser(self, tmp_path):
        """_get_domain returns empty string when browser is unhealthy."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.is_awake = False
        agent.hand = mock_hand

        result = agent._get_domain()

        assert result == ""

    def test_get_domain_handles_exception(self, tmp_path):
        """_get_domain returns empty string when get_url() raises."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.is_awake = True
        mock_hand.get_url.side_effect = BrowserError("Page closed")
        agent.hand = mock_hand

        result = agent._get_domain()

        assert result == ""


# =============================================================================
# Integration Tests
# =============================================================================

class TestBrowserHealthCheckInStep:
    """Tests for browser health check integration in _step method."""

    def test_step_checks_health_first(self, tmp_path):
        """_step checks browser health at start."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = Mock()
        mock_hand.is_healthy.return_value = True
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_html.return_value = "<html><body><a href='/'>link</a></body></html>"
        mock_hand.get_title.return_value = "Test"
        agent.hand = mock_hand

        # Full debug_html return structure
        debug_html_return = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 10,
            "raw_links": 1,
            "raw_inputs": 0
        }

        # Patch to prevent full step execution
        with patch.object(agent, 'check_browser_health', return_value=True) as mock_check, \
             patch.object(agent.eyes, 'see', return_value={"links": [], "buttons": [], "inputs": []}), \
             patch.object(agent.eyes, 'debug_html', return_value=debug_html_return), \
             patch.object(agent.llm, 'generate', return_value='{"action": "done", "reason": "test"}'):

            agent._step("test goal", 1, quiet=True)

            mock_check.assert_called()


class TestRunMethodBrowserInitialization:
    """Tests for run() method browser initialization."""

    def test_run_returns_error_when_browser_fails(self, tmp_path):
        """run() returns error dict when browser fails to start."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(agent, 'ensure_browser', return_value=False):
            result = agent.run("test goal", quiet=True)

        assert result["success"] is False
        assert "error" in result
        assert "browser" in result["error"].lower()


class TestResumeMethodBrowserInitialization:
    """Tests for resume() method browser initialization."""

    def test_resume_returns_error_when_browser_fails(self, tmp_path):
        """resume() returns error dict when browser fails to start."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Mock persistent memory to return a valid session
        agent.persistent_memory.load_session_state = Mock(return_value={
            "session_id": 1,
            "goal": "test goal",
            "current_step": 1,
            "session_memory": agent.session_memory,
            "start_url": "https://google.com",
            "max_steps": 50,
            "current_url": "https://example.com"
        })

        with patch.object(agent, 'ensure_browser', return_value=False):
            result = agent.resume(1, quiet=True)

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Edge Cases
# =============================================================================

class TestBrowserManagementEdgeCases:
    """Edge case tests for browser management."""

    def test_multiple_restarts(self, tmp_path):
        """Multiple restarts work correctly."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(Hand, 'restart', return_value=True):
            for _ in range(3):
                result = agent.restart_browser()
                assert result is True

    def test_ensure_browser_after_restart(self, tmp_path):
        """ensure_browser works after restart."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(Hand, 'ensure_awake', return_value=True), \
             patch.object(Hand, 'restart', return_value=True):

            agent.ensure_browser()
            agent.restart_browser()
            result = agent.ensure_browser()

            assert result is True

    def test_health_tracking_persistence(self):
        """Health tracking state persists across calls."""
        hand = Hand()

        mock_page = Mock()
        type(mock_page).url = PropertyMock(side_effect=PlaywrightError("Error"))

        hand._playwright = Mock()
        hand._browser = Mock()
        hand._page = mock_page

        # Multiple failed health checks should accumulate errors
        hand.is_healthy()
        hand.is_healthy()
        hand.is_healthy()

        assert hand._consecutive_errors == 3
