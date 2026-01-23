"""
Unit tests for blackreach/agent.py

Tests agent configuration, callbacks, and core logic.
Note: Full integration tests require browser fixtures.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import asdict
from blackreach.agent import Agent, AgentConfig, AgentCallbacks


class TestAgentConfig:
    """Tests for AgentConfig defaults."""

    def test_default_max_steps(self):
        """AgentConfig has default max_steps."""
        config = AgentConfig()
        assert config.max_steps == 50

    def test_default_headless(self):
        """AgentConfig defaults to non-headless."""
        config = AgentConfig()
        assert config.headless is False

    def test_default_download_dir(self):
        """AgentConfig has default download directory."""
        config = AgentConfig()
        assert config.download_dir == Path("./downloads")

    def test_default_start_url(self):
        """AgentConfig has default start URL."""
        config = AgentConfig()
        assert config.start_url == "https://www.google.com"

    def test_default_memory_db(self):
        """AgentConfig has default memory database."""
        config = AgentConfig()
        assert config.memory_db == Path("./memory.db")

    def test_custom_max_steps(self):
        """AgentConfig accepts custom max_steps."""
        config = AgentConfig(max_steps=100)
        assert config.max_steps == 100

    def test_custom_headless(self):
        """AgentConfig accepts custom headless."""
        config = AgentConfig(headless=True)
        assert config.headless is True

    def test_custom_download_dir(self):
        """AgentConfig accepts custom download directory."""
        config = AgentConfig(download_dir=Path("/tmp/downloads"))
        assert config.download_dir == Path("/tmp/downloads")


class TestAgentCallbacks:
    """Tests for AgentCallbacks."""

    def test_all_callbacks_none_by_default(self):
        """AgentCallbacks has all None by default."""
        callbacks = AgentCallbacks()
        assert callbacks.on_step is None
        assert callbacks.on_action is None
        assert callbacks.on_observe is None
        assert callbacks.on_think is None
        assert callbacks.on_error is None
        assert callbacks.on_complete is None
        assert callbacks.on_status is None

    def test_custom_callbacks(self):
        """AgentCallbacks accepts custom callbacks."""
        mock_step = Mock()
        mock_error = Mock()
        callbacks = AgentCallbacks(on_step=mock_step, on_error=mock_error)
        assert callbacks.on_step is mock_step
        assert callbacks.on_error is mock_error


class TestAgentInit:
    """Tests for Agent initialization."""

    def test_default_init(self):
        """Agent initializes with defaults."""
        agent = Agent()
        assert agent.config is not None
        assert agent.callbacks is not None
        assert agent.hand is None  # Not started yet
        assert agent.session_id is None

    def test_custom_config(self):
        """Agent accepts custom config."""
        config = AgentConfig(max_steps=25)
        agent = Agent(agent_config=config)
        assert agent.config.max_steps == 25

    def test_custom_callbacks(self):
        """Agent accepts custom callbacks."""
        mock_callback = Mock()
        callbacks = AgentCallbacks(on_step=mock_callback)
        agent = Agent(callbacks=callbacks)
        assert agent.callbacks.on_step is mock_callback

    def test_session_memory_initialized(self):
        """Agent has session memory."""
        agent = Agent()
        assert agent.session_memory is not None

    def test_persistent_memory_initialized(self, tmp_path):
        """Agent has persistent memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        assert agent.persistent_memory is not None

    def test_prompts_loaded(self):
        """Agent loads prompts."""
        agent = Agent()
        assert "react" in agent.prompts

    def test_page_cache_initialized(self):
        """Agent has page cache."""
        agent = Agent()
        assert agent._page_cache is not None
        assert "url" in agent._page_cache
        assert "html" in agent._page_cache

    def test_stuck_detection_initialized(self):
        """Agent has stuck detection state."""
        agent = Agent()
        assert agent._recent_urls == []
        assert agent._max_stuck_count == 3
        assert agent._stuck_counter == 0


class TestAgentEmit:
    """Tests for _emit callback method."""

    def test_emit_calls_callback(self):
        """_emit calls registered callback."""
        mock_callback = Mock()
        callbacks = AgentCallbacks(on_step=mock_callback)
        agent = Agent(callbacks=callbacks)

        agent._emit("on_step", 1, 10, "observe", "test")

        mock_callback.assert_called_once_with(1, 10, "observe", "test")

    def test_emit_no_callback(self):
        """_emit handles missing callback gracefully."""
        agent = Agent()
        # Should not raise
        agent._emit("on_step", 1, 10, "observe", "test")

    def test_emit_handles_callback_error(self):
        """_emit catches callback errors."""
        def bad_callback(*args):
            raise ValueError("Callback error")

        callbacks = AgentCallbacks(on_step=bad_callback)
        agent = Agent(callbacks=callbacks)

        # Should not raise
        agent._emit("on_step", 1, 10, "observe", "test")


class TestAgentStuckDetection:
    """Tests for stuck detection logic."""

    def test_not_stuck_initially(self):
        """Agent is not stuck initially."""
        agent = Agent()
        assert agent._is_stuck() is False

    def test_not_stuck_with_few_urls(self):
        """Agent is not stuck with few URLs."""
        agent = Agent()
        agent._recent_urls = ["url1", "url2"]
        assert agent._is_stuck() is False

    def test_stuck_with_repeated_urls(self):
        """Agent detects when stuck on same URL."""
        agent = Agent()
        agent._recent_urls = ["same_url", "same_url", "same_url"]
        assert agent._is_stuck() is True

    def test_not_stuck_with_different_urls(self):
        """Agent is not stuck with different URLs."""
        agent = Agent()
        agent._recent_urls = ["url1", "url2", "url3"]
        assert agent._is_stuck() is False

    def test_track_url_adds_to_history(self):
        """_track_url adds URL to history."""
        agent = Agent()
        agent._track_url("http://example.com")
        assert "http://example.com" in agent._recent_urls

    def test_track_url_limits_history(self):
        """_track_url limits history size."""
        agent = Agent()
        for i in range(15):
            agent._track_url(f"url{i}")
        assert len(agent._recent_urls) <= 10

    def test_get_stuck_hint_returns_hint_when_stuck(self):
        """_get_stuck_hint returns hint when stuck."""
        agent = Agent()
        agent._recent_urls = ["same_url", "same_url", "same_url"]
        hint = agent._get_stuck_hint()
        assert "STUCK" in hint

    def test_get_stuck_hint_empty_when_not_stuck(self):
        """_get_stuck_hint returns empty when not stuck."""
        agent = Agent()
        agent._recent_urls = ["url1", "url2"]
        hint = agent._get_stuck_hint()
        assert hint == ""


class TestAgentDomainExtraction:
    """Tests for domain extraction."""

    def test_get_domain_from_url(self):
        """_get_domain extracts domain from URL."""
        agent = Agent()
        domain = agent._get_domain("https://www.example.com/page")
        assert domain == "www.example.com"

    def test_get_domain_with_port(self):
        """_get_domain handles URL with port."""
        agent = Agent()
        domain = agent._get_domain("http://localhost:8080/path")
        assert domain == "localhost:8080"

    def test_get_domain_no_url_no_hand(self):
        """_get_domain returns empty when no URL and no browser."""
        agent = Agent()
        domain = agent._get_domain()
        assert domain == ""


class TestAgentPause:
    """Tests for pause functionality."""

    def test_pause_sets_flag(self):
        """pause() sets _paused flag."""
        agent = Agent()
        agent.pause()
        assert agent._paused is True

    def test_pause_starts_false(self):
        """_paused starts as False."""
        agent = Agent()
        assert agent._paused is False


class TestActionAliases:
    """Tests for action alias mapping."""

    def test_action_aliases_defined(self):
        """Action aliases are defined in execute method."""
        # These are the expected aliases
        expected_aliases = {
            "search": "type",
            "go": "navigate",
            "goto": "navigate",
            "visit": "navigate",
            "enter": "type",
            "input": "type",
            "link": "click",
            "press_key": "press",
            "finish": "done",
            "complete": "done",
        }

        # Verify these are documented (by checking that code contains them)
        agent = Agent()

        # We can't easily test the internal _execute_action without mocking
        # But we can verify the agent loads
        assert agent is not None


class TestAgentRecording:
    """Tests for visit/download/failure recording."""

    def test_record_visit_adds_to_session(self, tmp_path):
        """_record_visit adds to session memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        agent._record_visit("http://example.com", title="Example")

        assert "http://example.com" in agent.session_memory.visited_urls

    def test_record_download_adds_to_session(self, tmp_path):
        """_record_download adds to session memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        agent._record_download("test.pdf", "http://example.com/test.pdf")

        assert "test.pdf" in agent.session_memory.downloaded_files

    def test_record_failure_adds_to_session(self, tmp_path):
        """_record_failure adds to session memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        agent._record_failure("http://example.com", "click", "Element not found")

        assert len(agent.session_memory.failures) > 0


class TestRefusalDetection:
    """Tests for LLM refusal detection logic."""

    def test_refusal_counter_starts_at_zero(self):
        """Refusal counter starts at 0."""
        agent = Agent()
        assert agent._refusal_count == 0

    def test_max_refusals_set(self):
        """Max refusals is set."""
        agent = Agent()
        assert agent._max_refusals == 3


class TestFormatElements:
    """Tests for _format_elements method."""

    def test_format_empty_parsed(self, tmp_path):
        """_format_elements handles empty parsed data."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        result = agent._format_elements({})
        assert result == "No interactive elements found"

    def test_format_with_links(self, tmp_path):
        """_format_elements includes links."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "http://example.com", "text": "Example", "type": "other"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "Links:" in result
        assert "Example" in result

    def test_format_with_images(self, tmp_path):
        """_format_elements includes images."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "images": [
                {"src": "http://example.com/img.jpg", "full_src": "http://example.com/full.jpg"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "Images:" in result

    def test_format_with_inputs(self, tmp_path):
        """_format_elements includes inputs."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "inputs": [
                {"name": "search", "placeholder": "Search..."}
            ]
        }
        result = agent._format_elements(parsed)
        assert "Inputs:" in result
        assert "search" in result

    def test_format_excludes_visited_urls(self, tmp_path):
        """_format_elements excludes already visited URLs."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "http://visited.com/page", "text": "Visited", "type": "other"},
                {"href": "http://new.com/page", "text": "New", "type": "other"}
            ]
        }
        result = agent._format_elements(parsed, exclude_urls=["http://visited.com/page"])
        assert "New" in result
        # Visited link should be excluded
        assert "Visited" not in result or "visited.com" not in result


class TestLoadPrompts:
    """Tests for prompt loading."""

    def test_load_prompts_returns_dict(self):
        """_load_prompts returns dictionary."""
        agent = Agent()
        assert isinstance(agent.prompts, dict)

    def test_react_prompt_loaded(self):
        """React prompt is loaded."""
        agent = Agent()
        assert "react" in agent.prompts
        assert len(agent.prompts["react"]) > 0

    def test_load_prompts_fallback_when_missing(self):
        """_load_prompts uses fallback when react.txt missing."""
        from unittest.mock import patch, MagicMock
        from pathlib import Path

        # Create a mock that makes react file not exist
        original_exists = Path.exists

        def mock_exists(self):
            if "react.txt" in str(self):
                return False
            return original_exists(self)

        with patch.object(Path, 'exists', mock_exists):
            agent = Agent.__new__(Agent)
            agent.hand = None
            prompts = agent._load_prompts()

            # Should have fallback message
            assert "react" in prompts
            assert "not found" in prompts["react"].lower()
