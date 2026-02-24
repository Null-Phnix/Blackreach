"""
Integration tests for blackreach/agent.py

These tests create actual Agent instances and test the complete workflow.
They require network access and may use LLM API calls.

Run with: pytest tests/test_integration_agent.py -v
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from blackreach.agent import Agent, AgentConfig, AgentCallbacks
from blackreach.llm import LLMConfig
from blackreach.browser import Hand
from blackreach.exceptions import UnknownActionError, InvalidActionArgsError, BrowserError


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def has_network():
    """Check if we have network access."""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


requires_network = pytest.mark.skipif(
    not has_network(),
    reason="No network access"
)


@pytest.fixture
def temp_memory_db(tmp_path):
    """Create a temporary memory database path."""
    return tmp_path / "test_memory.db"


@pytest.fixture
def agent_config(temp_memory_db, tmp_path):
    """Create a basic agent configuration."""
    return AgentConfig(
        memory_db=temp_memory_db,
        headless=True,
        max_steps=3,
        download_dir=tmp_path / "downloads"
    )


@pytest.fixture
def llm_config():
    """Create a basic LLM configuration."""
    return LLMConfig(
        provider="ollama",
        model="qwen2.5:7b",
        max_retries=1
    )


# =============================================================================
# Agent Creation Tests
# =============================================================================

class TestAgentCreation:
    """Tests for Agent instantiation."""

    def test_agent_creates_with_defaults(self, temp_memory_db):
        """Agent creates with default configuration."""
        config = AgentConfig(memory_db=temp_memory_db)
        agent = Agent(agent_config=config)

        assert agent is not None
        assert agent.config is not None

    def test_agent_creates_with_custom_config(self, agent_config):
        """Agent creates with custom configuration."""
        agent = Agent(agent_config=agent_config)

        assert agent.config.max_steps == 3
        assert agent.config.headless is True

    def test_agent_creates_with_llm_config(self, agent_config, llm_config):
        """Agent creates with LLM configuration."""
        agent = Agent(agent_config=agent_config, llm_config=llm_config)

        assert agent.llm is not None
        assert agent.llm.config.provider == "ollama"

    def test_agent_initializes_memory(self, agent_config):
        """Agent initializes persistent memory."""
        agent = Agent(agent_config=agent_config)

        assert agent.persistent_memory is not None
        stats = agent.persistent_memory.get_stats()
        assert stats is not None

    def test_agent_initializes_session_memory(self, agent_config):
        """Agent initializes session memory."""
        agent = Agent(agent_config=agent_config)

        assert agent.session_memory is not None

    def test_agent_loads_prompts(self, agent_config):
        """Agent loads prompt templates."""
        agent = Agent(agent_config=agent_config)

        assert agent.prompts is not None
        assert "react" in agent.prompts


# =============================================================================
# Agent Configuration Tests
# =============================================================================

class TestAgentConfiguration:
    """Tests for Agent configuration handling."""

    def test_agent_respects_max_steps(self, agent_config):
        """Agent respects max_steps configuration."""
        agent_config.max_steps = 5
        agent = Agent(agent_config=agent_config)

        assert agent.config.max_steps == 5

    def test_agent_respects_headless(self, agent_config):
        """Agent respects headless configuration."""
        agent_config.headless = True
        agent = Agent(agent_config=agent_config)

        assert agent.config.headless is True

    def test_agent_respects_download_dir(self, agent_config, tmp_path):
        """Agent respects download_dir configuration."""
        dl_dir = tmp_path / "custom_downloads"
        agent_config.download_dir = dl_dir
        agent = Agent(agent_config=agent_config)

        assert agent.config.download_dir == dl_dir


# =============================================================================
# Agent Callbacks Tests
# =============================================================================

class TestAgentCallbacks:
    """Tests for Agent callback system."""

    def test_agent_accepts_callbacks(self, agent_config):
        """Agent accepts callback configuration."""
        callbacks = AgentCallbacks(
            on_step=lambda *args: None,
            on_action=lambda *args: None,
            on_complete=lambda *args: None
        )
        agent = Agent(agent_config=agent_config, callbacks=callbacks)

        assert agent.callbacks is not None

    def test_agent_emits_callbacks(self, agent_config):
        """Agent emits callbacks when events occur."""
        events = []

        def on_status(msg):
            events.append(("status", msg))

        callbacks = AgentCallbacks(on_status=on_status)
        agent = Agent(agent_config=agent_config, callbacks=callbacks)

        # Trigger an event
        agent._emit("on_status", "Test message")

        assert len(events) > 0
        assert events[0][0] == "status"


# =============================================================================
# Smart Start URL Tests
# =============================================================================

class TestAgentSmartStartUrl:
    """Tests for _get_smart_start_url method."""

    def test_extracts_full_url(self, agent_config):
        """Extracts full URL from goal."""
        agent = Agent(agent_config=agent_config)

        url, reasoning, _ = agent._get_smart_start_url(
            "go to https://example.com",
            quiet=True
        )

        assert url == "https://example.com"
        assert "specified" in reasoning.lower()

    def test_extracts_bare_domain(self, agent_config):
        """Extracts bare domain from goal."""
        agent = Agent(agent_config=agent_config)

        url, reasoning, _ = agent._get_smart_start_url(
            "visit google.com",
            quiet=True
        )

        # google.com is blocked in headless mode — redirects to Bing
        assert "bing.com" in url
        assert "blocked" in reasoning.lower() or "bing" in reasoning.lower()

    def test_uses_knowledge_base(self, agent_config):
        """Uses knowledge base for generic goals."""
        agent = Agent(agent_config=agent_config)

        url, reasoning, _ = agent._get_smart_start_url(
            "find some research papers",
            quiet=True
        )

        assert url.startswith("https://")


# =============================================================================
# Session Management Tests
# =============================================================================

class TestAgentSessionManagement:
    """Tests for Agent session management."""

    def test_starts_session(self, agent_config):
        """Agent can start a session."""
        agent = Agent(agent_config=agent_config)

        session_id = agent.persistent_memory.start_session("test goal")

        assert session_id is not None
        assert session_id > 0

    def test_tracks_visited_urls(self, agent_config):
        """Agent tracks visited URLs in session memory."""
        agent = Agent(agent_config=agent_config)

        agent._record_visit("https://example.com")

        assert "https://example.com" in agent.session_memory.visited_urls


# =============================================================================
# Stuck Detection Tests
# =============================================================================

class TestAgentStuckDetection:
    """Tests for Agent stuck detection."""

    def test_detects_stuck_state(self, agent_config):
        """Agent detects when stuck on same URL."""
        agent = Agent(agent_config=agent_config)

        # Simulate being stuck
        for _ in range(5):
            agent._track_url("https://same-url.com")

        hint = agent._get_stuck_hint()

        assert hint is not None
        assert "STUCK" in hint

    def test_no_stuck_with_varied_urls(self, agent_config):
        """Agent doesn't report stuck with varied URLs."""
        agent = Agent(agent_config=agent_config)

        agent._track_url("https://url1.com")
        agent._track_url("https://url2.com")
        agent._track_url("https://url3.com")

        hint = agent._get_stuck_hint()

        # Should be empty string or None when not stuck
        assert hint == "" or hint is None


# =============================================================================
# Domain Extraction Tests
# =============================================================================

class TestAgentDomainExtraction:
    """Tests for Agent domain extraction."""

    def test_extracts_domain_from_url(self, agent_config):
        """Agent extracts domain from URL parameter."""
        agent = Agent(agent_config=agent_config)

        domain = agent._get_domain("https://www.example.com/path")

        assert domain == "www.example.com"

    def test_handles_missing_url(self, agent_config):
        """Agent handles missing URL gracefully."""
        agent = Agent(agent_config=agent_config)
        # No hand, no url parameter

        domain = agent._get_domain()

        assert domain == ""  # Returns empty string, not None


# =============================================================================
# State Save/Load Tests
# =============================================================================

class TestAgentStatePersistence:
    """Tests for Agent state save/load."""

    def test_saves_state(self, agent_config):
        """Agent can save state."""
        agent = Agent(agent_config=agent_config)
        agent._current_goal = "test goal"
        agent._current_step = 5

        # Should not raise
        agent.save_state()

    def test_loads_prompts(self, agent_config):
        """Agent loads prompts from YAML."""
        agent = Agent(agent_config=agent_config)

        # Should have react prompt
        assert "react" in agent.prompts
        assert len(agent.prompts["react"]) > 0


# =============================================================================
# Eyes (Observer) Integration Tests
# =============================================================================

class TestAgentEyesIntegration:
    """Tests for Agent Eyes (observer) integration."""

    def test_has_eyes(self, agent_config):
        """Agent has Eyes (observer) instance."""
        agent = Agent(agent_config=agent_config)

        assert agent.eyes is not None

    def test_eyes_can_parse_html(self, agent_config):
        """Agent's Eyes can parse HTML."""
        agent = Agent(agent_config=agent_config)

        html = "<html><body><a href='/test'>Link</a></body></html>"
        result = agent.eyes.see(html)

        assert result is not None


# =============================================================================
# Format Elements Tests
# =============================================================================

class TestAgentFormatElements:
    """Tests for Agent element formatting."""

    def test_formats_links(self, agent_config):
        """Agent formats links for LLM."""
        agent = Agent(agent_config=agent_config)

        parsed = {
            "links": [{"text": "Test Link", "href": "/test"}],
            "inputs": [],
            "buttons": [],
            "images": [],
            "text_content": "Page text"
        }

        elements = agent._format_elements(parsed)

        assert "Test Link" in elements or "link" in elements.lower()

    def test_formats_inputs(self, agent_config):
        """Agent formats inputs for LLM."""
        agent = Agent(agent_config=agent_config)

        parsed = {
            "links": [],
            "inputs": [{"type": "text", "name": "search", "placeholder": "Search..."}],
            "buttons": [],
            "images": [],
            "text_content": ""
        }

        elements = agent._format_elements(parsed)

        assert "search" in elements.lower() or "input" in elements.lower()

    def test_handles_empty_page(self, agent_config):
        """Agent handles empty page gracefully."""
        agent = Agent(agent_config=agent_config)

        parsed = {
            "links": [],
            "inputs": [],
            "buttons": [],
            "images": [],
            "text_content": ""
        }

        elements = agent._format_elements(parsed)

        assert elements is not None


# =============================================================================
# Action Normalization Tests
# =============================================================================

class TestAgentActionNormalization:
    """Tests for Agent action alias handling."""

    def test_normalizes_action_aliases(self, agent_config):
        """Agent normalizes action aliases in _execute_action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.goto.return_value = {"action": "goto", "success": True}
        agent.hand.get_url.return_value = "https://other.com"  # Different URL to avoid skip

        # "goto" is an alias for "navigate"
        result = agent._execute_action("goto", {"url": "https://example.com"})

        assert result is not None
        agent.hand.goto.assert_called()

    def test_handles_done_action(self, agent_config):
        """Agent handles done action."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("done", {"reason": "Goal complete"})

        assert result is not None
        assert result.get("done") is True

    def test_handles_wait_action(self, agent_config):
        """Agent handles wait action."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("wait", {"seconds": 0.1})

        assert result is not None
        assert result.get("action") == "wait"


# =============================================================================
# Integration with Browser Tests
# =============================================================================

class TestAgentBrowserIntegration:
    """Tests for Agent integration with browser."""

    @requires_network
    def test_agent_can_wake_browser(self, agent_config, llm_config):
        """Agent can wake the browser."""
        agent = Agent(agent_config=agent_config, llm_config=llm_config)

        # Manually create and wake hand
        agent.hand = Hand(
            headless=True,
            download_dir=agent.config.download_dir
        )
        agent.hand.wake()

        assert agent.hand is not None
        assert agent.hand._browser is not None

        agent.hand.sleep()

    @requires_network
    def test_agent_can_navigate(self, agent_config, llm_config):
        """Agent can navigate with browser."""
        agent = Agent(agent_config=agent_config, llm_config=llm_config)

        agent.hand = Hand(
            headless=True,
            download_dir=agent.config.download_dir
        )
        agent.hand.wake()

        result = agent.hand.goto("https://www.google.com")

        assert result is not None
        assert "google" in agent.hand.get_url().lower()

        agent.hand.sleep()


# =============================================================================
# Refusal Handling Tests
# =============================================================================

class TestAgentRefusalHandling:
    """Tests for Agent refusal handling attributes."""

    def test_has_refusal_counter(self, agent_config):
        """Agent has refusal counter."""
        agent = Agent(agent_config=agent_config)

        assert hasattr(agent, '_refusal_count')
        assert agent._refusal_count == 0

    def test_has_max_refusals_setting(self, agent_config):
        """Agent has max refusals setting."""
        agent = Agent(agent_config=agent_config)

        assert hasattr(agent, '_max_refusals')
        assert agent._max_refusals == 3


# =============================================================================
# Action Execution Tests (Mocked)
# =============================================================================

class TestAgentActionExecution:
    """Tests for Agent action execution with mocked browser."""

    def test_execute_click_action(self, agent_config):
        """Agent executes click action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.click.return_value = {"action": "click", "success": True}

        result = agent._execute_action("click", {"selector": "#btn"})

        assert result is not None
        agent.hand.click.assert_called()

    def test_execute_type_action(self, agent_config):
        """Agent executes type action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.type.return_value = {"action": "type", "success": True}
        agent.hand.page = Mock()
        agent.hand.page.keyboard = Mock()

        result = agent._execute_action("type", {"selector": "input", "text": "test"})

        assert result is not None
        agent.hand.type.assert_called()

    def test_execute_navigate_action(self, agent_config):
        """Agent executes navigate action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.goto.return_value = {"action": "goto", "success": True}
        agent.hand.get_url.return_value = "https://other.com"

        result = agent._execute_action("navigate", {"url": "https://example.com"})

        assert result is not None
        agent.hand.goto.assert_called()

    def test_execute_scroll_action(self, agent_config):
        """Agent executes scroll action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.scroll.return_value = {"action": "scroll", "success": True}

        result = agent._execute_action("scroll", {"direction": "down", "amount": 300})

        assert result is not None
        agent.hand.scroll.assert_called()

    def test_execute_done_action(self, agent_config):
        """Agent handles done action."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("done", {"reason": "Downloaded all files"})

        assert result is not None
        assert result.get("done") is True

    def test_execute_back_action(self, agent_config):
        """Agent executes back action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.back.return_value = {"action": "back", "success": True}

        result = agent._execute_action("back", {})

        assert result is not None
        agent.hand.back.assert_called()

    def test_execute_press_action(self, agent_config):
        """Agent executes press action."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.page = Mock()
        agent.hand.page.keyboard = Mock()

        result = agent._execute_action("press", {"key": "Enter"})

        assert result is not None
        assert result.get("action") == "press"

    def test_execute_navigate_skips_same_url(self, agent_config):
        """Agent skips navigation to same URL."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.get_url.return_value = "https://example.com"

        result = agent._execute_action("navigate", {"url": "https://example.com"})

        assert result is not None
        assert result.get("skipped") is True
        agent.hand.goto.assert_not_called()

    def test_execute_navigate_resolves_relative_url(self, agent_config):
        """Agent resolves relative URLs."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.get_url.return_value = "https://example.com/page"
        agent.hand.goto.return_value = {"action": "goto", "success": True}

        result = agent._execute_action("navigate", {"url": "/other"})

        assert result is not None
        # Should have resolved to absolute URL
        agent.hand.goto.assert_called()

    def test_execute_type_without_submit(self, agent_config):
        """Agent types without submit."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.type.return_value = {"action": "type", "success": True}
        agent.hand.page = Mock()

        result = agent._execute_action("type", {
            "selector": "input",
            "text": "test",
            "submit": False
        })

        assert result is not None
        assert result.get("submit") is False
        # Should NOT call keyboard.press for Enter
        agent.hand.page.keyboard.press.assert_not_called()

    def test_execute_search_alias(self, agent_config):
        """Agent handles 'search' as alias for 'type'."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.type.return_value = {"action": "type", "success": True}
        agent.hand.page = Mock()
        agent.hand.page.keyboard = Mock()

        result = agent._execute_action("search", {"text": "query"})

        assert result is not None
        agent.hand.type.assert_called()

    def test_execute_visit_alias(self, agent_config):
        """Agent handles 'visit' as alias for 'navigate'."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.goto.return_value = {"action": "goto", "success": True}
        agent.hand.get_url.return_value = "https://other.com"

        result = agent._execute_action("visit", {"url": "https://example.com"})

        assert result is not None
        agent.hand.goto.assert_called()

    def test_execute_link_alias(self, agent_config):
        """Agent handles 'link' as alias for 'click'."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.click.return_value = {"action": "click", "success": True}

        result = agent._execute_action("link", {"selector": "#mylink"})

        assert result is not None
        agent.hand.click.assert_called()

    def test_execute_finish_alias(self, agent_config):
        """Agent handles 'finish' as alias for 'done'."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("finish", {"reason": "Complete"})

        assert result is not None
        assert result.get("done") is True

    def test_execute_complete_alias(self, agent_config):
        """Agent handles 'complete' as alias for 'done'."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("complete", {"reason": "Done"})

        assert result is not None
        assert result.get("done") is True

    def test_execute_unknown_action_raises(self, agent_config):
        """Agent raises UnknownActionError for unknown actions."""
        agent = Agent(agent_config=agent_config)

        with pytest.raises(UnknownActionError):
            agent._execute_action("unknown_action_xyz", {})

    def test_execute_click_without_args_raises(self, agent_config):
        """Agent raises InvalidActionArgsError for click without args."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        # Mock the page to fail text-based click
        agent.hand.page = Mock()
        agent.hand.page.get_by_text.side_effect = Exception("Not found")
        agent.hand.page.locator.return_value = Mock(count=Mock(return_value=0))

        with pytest.raises(InvalidActionArgsError):
            agent._execute_action("click", {})

    def test_execute_wait_action(self, agent_config):
        """Agent executes wait action."""
        agent = Agent(agent_config=agent_config)

        result = agent._execute_action("wait", {"seconds": 0.01})

        assert result is not None
        assert result.get("action") == "wait"

    def test_execute_scroll_defaults(self, agent_config):
        """Agent uses scroll defaults."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.scroll.return_value = {"action": "scroll", "success": True}

        result = agent._execute_action("scroll", {})  # No direction specified

        assert result is not None
        assert result.get("direction") == "down"  # Default


# =============================================================================
# Click Action Edge Cases
# =============================================================================

class TestAgentClickAction:
    """Tests for click action edge cases."""

    def test_click_with_text_arg(self, agent_config):
        """Agent can click by text content."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.page = Mock()
        agent.hand.page.get_by_text.return_value.first.click.return_value = None

        result = agent._execute_action("click", {"text": "Submit"})

        assert result is not None
        assert result.get("text") == "Submit"

    def test_click_text_strips_brackets(self, agent_config):
        """Agent strips brackets from text arg."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.page = Mock()
        agent.hand.page.get_by_text.return_value.first.click.return_value = None

        result = agent._execute_action("click", {"text": "[Submit Button]"})

        assert result is not None
        # Text should be stripped
        assert result.get("text") == "Submit Button"

    def test_click_falls_back_to_selector(self, agent_config):
        """Agent falls back to selector when text fails."""
        agent = Agent(agent_config=agent_config)
        agent.hand = Mock()
        agent.hand.page = Mock()
        # Make text-based click fail
        agent.hand.page.get_by_text.side_effect = BrowserError("Not found")
        agent.hand.click.return_value = {"action": "click", "success": True}

        result = agent._execute_action("click", {
            "text": "Not Found",
            "selector": "#fallback"
        })

        assert result is not None
        agent.hand.click.assert_called_with("#fallback")
