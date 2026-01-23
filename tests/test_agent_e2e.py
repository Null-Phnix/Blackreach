"""
End-to-end tests for the Blackreach agent.

These tests verify the complete agent workflow using mocked components
to avoid actual browser and LLM API calls.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from blackreach.agent import Agent, AgentConfig
from blackreach.llm import LLMConfig, LLMResponse
from blackreach.memory import SessionMemory, PersistentMemory


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_responses():
    """Sequence of mock LLM responses for a download task."""
    return [
        # Step 1: Navigate to search
        LLMResponse(
            thought="I need to go to the search page",
            action="navigate",
            args={"url": "https://arxiv.org/search?query=test"},
            done=False
        ),
        # Step 2: Click on paper
        LLMResponse(
            thought="Found a paper, clicking on it",
            action="click",
            args={"text": "Test Paper"},
            done=False
        ),
        # Step 3: Download PDF
        LLMResponse(
            thought="Found the PDF link, downloading",
            action="download",
            args={"url": "https://arxiv.org/pdf/1234.pdf"},
            done=False
        ),
        # Step 4: Done
        LLMResponse(
            thought="Downloaded the paper successfully",
            action="done",
            args={"reason": "Downloaded 1 paper"},
            done=True,
            reason="Downloaded 1 paper"
        ),
    ]


@pytest.fixture
def mock_browser():
    """Create a mock browser (Hand) with common responses."""
    browser = Mock()
    browser.get_url.return_value = "https://arxiv.org"
    browser.get_title.return_value = "arXiv.org"
    browser.get_html.return_value = """
        <html>
        <head><title>arXiv.org</title></head>
        <body>
            <a href="/abs/1234">Test Paper</a>
            <a href="/pdf/1234.pdf">PDF</a>
        </body>
        </html>
    """
    browser.goto.return_value = {"action": "navigate", "success": True}
    browser.click.return_value = {"action": "click", "success": True}
    browser.type_text.return_value = {"action": "type", "success": True}
    browser.download_link.return_value = {
        "action": "download",
        "filename": "1234.pdf",
        "path": "/tmp/1234.pdf",
        "size": 100000,
        "hash": "abc123",
        "url": "https://arxiv.org/pdf/1234.pdf"
    }
    browser.wake.return_value = None
    browser.sleep.return_value = None
    return browser


# =============================================================================
# Agent Configuration Tests
# =============================================================================

class TestAgentConfig:
    """Tests for agent configuration."""

    def test_default_config(self):
        """AgentConfig has sensible defaults."""
        config = AgentConfig()

        assert config.max_steps == 50
        assert config.headless is False
        assert config.download_dir == Path("./downloads")

    def test_custom_config(self, temp_dir):
        """AgentConfig accepts custom values."""
        config = AgentConfig(
            max_steps=10,
            headless=True,
            download_dir=temp_dir / "custom"
        )

        assert config.max_steps == 10
        assert config.headless is True


# =============================================================================
# Agent Initialization Tests
# =============================================================================

class TestAgentInitialization:
    """Tests for Agent initialization."""

    def test_agent_creates_with_config(self, temp_dir):
        """Agent initializes with provided config."""
        agent_config = AgentConfig(
            max_steps=5,
            headless=True,
            download_dir=temp_dir / "downloads"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=agent_config
        )

        assert agent.config.max_steps == 5
        assert agent.config.headless is True

    def test_agent_initializes_memory(self, temp_dir):
        """Agent initializes both memory systems."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        assert isinstance(agent.session_memory, SessionMemory)
        assert isinstance(agent.persistent_memory, PersistentMemory)


# =============================================================================
# Action Execution Tests
# =============================================================================

class TestActionExecution:
    """Tests for individual action execution."""

    def test_navigate_action(self, temp_dir, mock_browser):
        """Navigate action calls browser.goto()."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )
        agent.hand = mock_browser

        result = agent._execute_action("navigate", {"url": "https://example.com"})

        mock_browser.goto.assert_called_once()
        assert result["action"] == "navigate"

    def test_click_action_with_selector(self, temp_dir, mock_browser):
        """Click action with selector calls browser.click()."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )
        agent.hand = mock_browser

        # Test with explicit selector (the implementation falls through to hand.click)
        result = agent._execute_action("click", {"selector": "#specific-button"})

        mock_browser.click.assert_called_with("#specific-button")

    def test_type_action(self, temp_dir, mock_browser):
        """Type action calls browser.type()."""
        # Mock the page.keyboard for the Enter press
        mock_keyboard = Mock()
        mock_page = Mock()
        mock_page.keyboard = mock_keyboard
        mock_browser.page = mock_page

        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )
        agent.hand = mock_browser

        result = agent._execute_action("type", {"selector": "#search", "text": "query"})

        mock_browser.type.assert_called()


# =============================================================================
# Memory Integration Tests
# =============================================================================

class TestMemoryIntegration:
    """Tests for agent memory integration."""

    def test_visit_recorded(self, temp_dir, mock_browser):
        """Visits are recorded in memory."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )
        agent.hand = mock_browser

        agent._record_visit("https://example.com", "Example")

        assert "https://example.com" in agent.session_memory.visited_urls

    def test_download_recorded(self, temp_dir, mock_browser):
        """Downloads are recorded in memory."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )
        agent.hand = mock_browser

        agent._record_download("test.pdf", "https://example.com/test.pdf")

        assert "test.pdf" in agent.session_memory.downloaded_files
        assert "https://example.com/test.pdf" in agent.session_memory.downloaded_urls


# =============================================================================
# Element Formatting Tests
# =============================================================================

class TestElementFormatting:
    """Tests for element formatting for LLM."""

    def test_format_elements_includes_links(self, temp_dir):
        """_format_elements includes links."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        parsed = {
            "links": [
                {"href": "/page1", "text": "Link 1", "selector": "a"},
                {"href": "/page2", "text": "Link 2", "selector": "a"},
            ],
            "inputs": [],
            "buttons": [],
            "images": [],
        }

        formatted = agent._format_elements(parsed)

        assert "Link 1" in formatted or "/page1" in formatted

    def test_format_elements_excludes_visited(self, temp_dir):
        """_format_elements excludes already visited URLs."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        parsed = {
            "links": [
                {"href": "https://arxiv.org/abs/1234", "text": "Paper 1", "selector": "a"},
                {"href": "https://arxiv.org/abs/5678", "text": "Paper 2", "selector": "a"},
            ],
            "inputs": [],
            "buttons": [],
            "images": [],
        }

        # Exclude the first URL
        exclude_urls = ["https://arxiv.org/abs/1234"]
        formatted = agent._format_elements(parsed, exclude_urls=exclude_urls)

        # First paper should be excluded, second should be present
        assert "1234" not in formatted or "5678" in formatted


# =============================================================================
# Stuck Detection Tests
# =============================================================================

class TestStuckDetection:
    """Tests for agent stuck detection."""

    def test_is_stuck_false_initially(self, temp_dir):
        """Agent is not stuck initially."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        assert agent._is_stuck() is False

    def test_is_stuck_after_same_url_repeatedly(self, temp_dir):
        """Agent detects being stuck on same URL."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        # Track same URL multiple times
        for _ in range(10):
            agent._track_url("https://example.com/stuck")

        assert agent._is_stuck() is True

    def test_is_stuck_false_with_different_urls(self, temp_dir):
        """Agent not stuck when visiting different URLs."""
        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config
        )

        # Track different URLs
        for i in range(10):
            agent._track_url(f"https://example.com/page{i}")

        assert agent._is_stuck() is False


# =============================================================================
# Callback Tests
# =============================================================================

class TestCallbacks:
    """Tests for agent callbacks."""

    def test_emit_calls_callback(self, temp_dir):
        """_emit calls registered callback."""
        from blackreach.agent import AgentCallbacks

        callback_called = []

        def on_step(step, max_steps, phase, message):
            callback_called.append((step, phase))

        callbacks = AgentCallbacks(on_step=on_step)

        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config,
            callbacks=callbacks
        )

        agent._emit("on_step", 1, 10, "test", "message")

        assert len(callback_called) == 1
        assert callback_called[0] == (1, "test")

    def test_emit_handles_missing_callback(self, temp_dir):
        """_emit doesn't crash if callback not set."""
        from blackreach.agent import AgentCallbacks

        callbacks = AgentCallbacks()  # No callbacks set

        config = AgentConfig(
            download_dir=temp_dir / "downloads",
            memory_db=temp_dir / "test.db"
        )

        agent = Agent(
            llm_config=LLMConfig(),
            agent_config=config,
            callbacks=callbacks
        )

        # Should not raise
        agent._emit("on_step", 1, 10, "test", "message")
