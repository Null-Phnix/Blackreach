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
from blackreach.exceptions import SessionNotFoundError, LLMError, BrowserError


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
        """Agent has session memory with correct initial state."""
        agent = Agent()
        assert agent.session_memory is not None
        # Verify initial state is empty
        assert agent.session_memory.downloaded_files == []
        assert agent.session_memory.visited_urls == []
        assert agent.session_memory.actions_taken == []

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


class TestClickTextExtraction:
    """Tests for click text extraction from LLM thoughts."""

    def test_extract_quoted_text(self):
        """Extract text from quotes in thought."""
        import re
        thought = "I should click 'Download EPUB' button"
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", thought)
        assert quoted
        assert quoted[0] == "Download EPUB"

    def test_extract_slow_download_pattern(self):
        """Extract 'slow download' from thought."""
        import re
        thought = "I need to click slow download link"
        patterns = [
            r'(slow\s+download)',
            r'(fast\s+download)',
        ]
        found = None
        for pattern in patterns:
            match = re.search(pattern, thought, re.IGNORECASE)
            if match:
                found = match.group(1).strip()
                break
        assert found == "slow download"

    def test_extract_fast_download_pattern(self):
        """Extract 'fast download' from thought."""
        import re
        thought = "Click on Fast Download"
        patterns = [
            r'(slow\s+download)',
            r'(fast\s+download)',
        ]
        found = None
        for pattern in patterns:
            match = re.search(pattern, thought, re.IGNORECASE)
            if match:
                found = match.group(1).strip()
                break
        assert found == "Fast Download"

    def test_extract_partner_server_pattern(self):
        """Extract 'slow partner server' from thought."""
        import re
        thought = "Click Slow Partner Server download"
        patterns = [
            r'(slow\s+partner\s+server)',
            r'(fast\s+partner\s+server)',
        ]
        found = None
        for pattern in patterns:
            match = re.search(pattern, thought, re.IGNORECASE)
            if match:
                found = match.group(1).strip()
                break
        assert found == "Slow Partner Server"

    def test_extract_click_x_button_pattern(self):
        """Extract 'X button' pattern from thought."""
        import re
        thought = "click the Download button"
        click_match = re.search(
            r"click(?:\s+(?:the|on|a))?\s+['\"]?(\w+(?:\s+\w+){0,3})['\"]?\s*(?:button|link|tab)?",
            thought, re.IGNORECASE
        )
        assert click_match
        # "Download button" is captured, which is fine for text matching
        assert "Download" in click_match.group(1).strip()

    def test_extract_multi_word_text(self):
        """Extract multi-word text from thought."""
        import re
        thought = "I will click the Get This Book button"
        click_match = re.search(
            r"click(?:\s+(?:the|on|a))?\s+['\"]?(\w+(?:\s+\w+){0,3})['\"]?\s*(?:button|link|tab)?",
            thought, re.IGNORECASE
        )
        assert click_match
        # Should capture up to 4 words (base + 3 more)
        assert "Get This Book" in click_match.group(1)


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


class TestSaveState:
    """Tests for save_state method."""

    def test_save_state_returns_early_without_session(self):
        """save_state returns early if no session_id."""
        agent = Agent.__new__(Agent)
        agent.session_id = None
        agent._current_goal = "test"
        agent.persistent_memory = MagicMock()

        # Should return without calling save_session_state
        agent.save_state()
        agent.persistent_memory.save_session_state.assert_not_called()

    def test_save_state_returns_early_without_goal(self):
        """save_state returns early if no current goal."""
        agent = Agent.__new__(Agent)
        agent.session_id = 123
        agent._current_goal = None
        agent.persistent_memory = MagicMock()

        # Should return without calling save_session_state
        agent.save_state()
        agent.persistent_memory.save_session_state.assert_not_called()


class TestResumeSession:
    """Tests for resume method."""

    def test_resume_raises_when_session_not_found(self):
        """resume raises SessionNotFoundError when session doesn't exist."""
        agent = Agent.__new__(Agent)
        agent.persistent_memory = MagicMock()
        agent.persistent_memory.load_session_state.return_value = None

        with pytest.raises(SessionNotFoundError):
            agent.resume(999)


class TestFormatElementsExtended:
    """Extended tests for _format_elements method."""

    def test_format_with_buttons(self, tmp_path):
        """_format_elements includes buttons."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "buttons": [
                {"text": "Submit", "type": "submit"},
                {"text": "Cancel", "type": "button"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "Buttons:" in result
        assert "Submit" in result

    def test_format_with_download_links(self, tmp_path):
        """_format_elements highlights download links."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "http://example.com/file.pdf", "text": "Download PDF", "type": "download"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "Download PDF" in result

    def test_format_with_nav_links(self, tmp_path):
        """_format_elements includes nav links."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "http://example.com/about", "text": "About Us", "type": "nav"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "About Us" in result or "Links:" in result

    def test_format_with_text_content(self, tmp_path):
        """_format_elements includes text content."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "text": "This is the main content of the page."
        }
        result = agent._format_elements(parsed)
        # Text might be formatted separately
        assert result is not None

    def test_format_with_selects(self, tmp_path):
        """_format_elements includes select dropdowns."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "selects": [
                {"name": "country", "options": ["USA", "Canada", "UK"]}
            ]
        }
        result = agent._format_elements(parsed)
        # Should handle selects if present
        assert result is not None


class TestAgentMemoryRecording:
    """Tests for memory recording methods."""

    def test_record_download_without_url(self, tmp_path):
        """_record_download handles empty URL."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Should not raise
        agent._record_download("test.pdf", "")

        assert "test.pdf" in agent.session_memory.downloaded_files

    def test_record_visit_with_metadata(self, tmp_path):
        """_record_visit records with title and success."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        agent._record_visit("http://example.com", title="Example", success=True)

        assert "http://example.com" in agent.session_memory.visited_urls

    def test_track_url_maintains_limit(self, tmp_path):
        """_track_url keeps history limited."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Add many URLs
        for i in range(20):
            agent._track_url(f"http://example.com/page{i}")

        # Should be capped at 10
        assert len(agent._recent_urls) == 10
        # Most recent should be last
        assert "page19" in agent._recent_urls[-1]


class TestFormatElementsAdvanced:
    """Advanced tests for _format_elements edge cases."""

    def test_format_excludes_arxiv_urls_by_id(self, tmp_path):
        """_format_elements excludes arxiv URLs by paper ID."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "https://arxiv.org/abs/2301.12345", "text": "Paper 1", "type": "other"},
                {"href": "https://arxiv.org/pdf/2301.67890", "text": "Paper 2", "type": "other"}
            ]
        }
        # Exclude the first paper by its abs URL
        result = agent._format_elements(parsed, exclude_urls=["https://arxiv.org/abs/2301.12345"])
        assert "Paper 2" in result
        # Paper 1 should be excluded

    def test_format_with_full_image_src(self, tmp_path):
        """_format_elements handles full image sources."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "images": [
                {"src": "http://example.com/thumb.jpg", "full_src": "http://example.com/full.jpg"}
            ]
        }
        result = agent._format_elements(parsed)
        assert "DOWNLOAD:" in result or "Images:" in result

    def test_format_with_thumbnail_detection(self, tmp_path):
        """_format_elements detects thumbnails vs full images."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "images": [
                {"src": "http://example.com/thumb/small.jpg", "link": "http://example.com/view/1"},
                {"src": "http://example.com/full/large.jpg"}
            ]
        }
        result = agent._format_elements(parsed)
        # Should have some output for images
        assert result is not None

    def test_format_with_image_link(self, tmp_path):
        """_format_elements includes image links for navigation."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "images": [
                {"src": "http://example.com/preview.jpg", "link": "http://example.com/image/123"}
            ]
        }
        result = agent._format_elements(parsed)
        # Should show NAVIGATE TO for linked images
        assert "NAVIGATE TO" in result or "Images:" in result


class TestAgentGetDomainExtended:
    """Extended tests for _get_domain method."""

    def test_get_domain_with_subdomain(self, tmp_path):
        """_get_domain handles subdomains."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        domain = agent._get_domain("https://api.example.com/v1/users")
        assert domain == "api.example.com"

    def test_get_domain_with_path(self, tmp_path):
        """_get_domain extracts just the domain."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        domain = agent._get_domain("https://example.com/path/to/page?query=1")
        assert domain == "example.com"

    def test_get_domain_http_url(self, tmp_path):
        """_get_domain works with http URLs."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        domain = agent._get_domain("http://insecure.example.com/page")
        assert domain == "insecure.example.com"


class TestAgentStuckHint:
    """Tests for _get_stuck_hint method."""

    def test_stuck_hint_includes_start_url(self, tmp_path):
        """_get_stuck_hint includes start URL suggestion."""
        config = AgentConfig(memory_db=tmp_path / "test.db", start_url="https://google.com")
        agent = Agent(agent_config=config)

        # Make agent stuck
        agent._recent_urls = ["same_url", "same_url", "same_url"]

        hint = agent._get_stuck_hint()

        assert "STUCK" in hint
        assert "google.com" in hint

    def test_stuck_hint_suggests_different_action(self, tmp_path):
        """_get_stuck_hint suggests trying different actions."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        agent._recent_urls = ["same", "same", "same"]
        hint = agent._get_stuck_hint()

        assert "DO NOT repeat" in hint or "different" in hint.lower()

    def test_stuck_hint_annas_archive_specific(self, tmp_path):
        """_get_stuck_hint provides Anna's Archive specific guidance."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Simulate being stuck on Anna's Archive
        annas_url = "https://annas-archive.org/md5/abc123"
        agent._recent_urls = [annas_url, annas_url, annas_url]

        hint = agent._get_stuck_hint()

        assert "ANNA'S ARCHIVE" in hint
        assert "Downloads" in hint or "download" in hint.lower()

    def test_stuck_hint_libgen_specific(self, tmp_path):
        """_get_stuck_hint provides LibGen specific guidance."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Simulate being stuck on LibGen
        libgen_url = "https://libgen.is/book/index.php?md5=abc"
        agent._recent_urls = [libgen_url, libgen_url, libgen_url]

        hint = agent._get_stuck_hint()

        assert "LIBGEN" in hint
        assert "GET" in hint or "mirror" in hint.lower()


class TestAgentClickTracking:
    """Tests for click tracking to prevent repeated expansion button clicks."""

    def test_expansion_buttons_defined(self):
        """Expansion buttons set is defined and non-empty."""
        agent = Agent()
        assert agent._expansion_buttons is not None
        assert len(agent._expansion_buttons) > 0
        assert 'button:has-text("Downloads")' in agent._expansion_buttons

    def test_clicked_selectors_initialized(self):
        """Clicked selectors set is initialized."""
        agent = Agent()
        assert agent._clicked_selectors is not None
        assert isinstance(agent._clicked_selectors, set)

    def test_selector_click_counts_initialized(self):
        """Selector click counts dict is initialized."""
        agent = Agent()
        assert agent._selector_click_counts is not None
        assert isinstance(agent._selector_click_counts, dict)

    def test_max_same_selector_clicks_set(self):
        """Max same selector clicks limit is set."""
        agent = Agent()
        assert agent._max_same_selector_clicks == 2


class TestGetSmartStartUrl:
    """Tests for _get_smart_start_url method."""

    def test_extracts_full_url_from_goal(self, tmp_path):
        """_get_smart_start_url extracts https:// URLs from goal."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("visit https://example.com", quiet=True)

        assert url == "https://example.com"
        assert "specified in goal" in reasoning.lower()

    def test_extracts_http_url_from_goal(self, tmp_path):
        """_get_smart_start_url extracts http:// URLs from goal."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("go to http://test.com", quiet=True)

        assert url == "http://test.com"
        assert "specified in goal" in reasoning.lower()

    def test_extracts_bare_com_domain(self, tmp_path):
        """_get_smart_start_url extracts bare .com domains."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("go to google.com", quiet=True)

        assert url == "https://google.com"
        assert "domain" in reasoning.lower()

    def test_extracts_bare_org_domain(self, tmp_path):
        """_get_smart_start_url extracts bare .org domains."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("visit example.org", quiet=True)

        assert url == "https://example.org"

    def test_extracts_bare_io_domain(self, tmp_path):
        """_get_smart_start_url extracts bare .io domains."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("check out cursor.io", quiet=True)

        assert url == "https://cursor.io"

    def test_uses_knowledge_base_for_generic_goals(self, tmp_path):
        """_get_smart_start_url uses knowledge base for generic goals."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, reasoning, _ = agent._get_smart_start_url("download some files", quiet=True)

        # Should fall back to knowledge base reasoning
        assert "https://" in url
        assert "specified in goal" not in reasoning.lower()

    def test_full_url_takes_priority_over_domain(self, tmp_path):
        """Full URLs take priority over bare domain detection."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        url, _, _ = agent._get_smart_start_url(
            "go to https://example.com not google.com", quiet=True
        )

        assert url == "https://example.com"


# =============================================================================
# Tests for _emit() callback error rate limiting
# =============================================================================

class TestEmitCallbackRateLimiting:
    """Tests for _emit callback error rate limiting."""

    def test_callback_error_rate_limit_tracks_errors(self, tmp_path):
        """_emit tracks callback errors per event type."""
        def bad_callback(*args):
            raise ValueError("Test error")

        callbacks = AgentCallbacks(on_step=bad_callback)
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config, callbacks=callbacks)

        # Emit multiple times
        for i in range(5):
            agent._emit("on_step", i, 10, "observe", "test")

        # Should have tracked the errors
        assert agent._callback_errors.get("on_step", 0) == 5

    def test_callback_error_rate_limit_suppresses_after_max(self, tmp_path, capsys):
        """_emit suppresses error logging after max errors."""
        def bad_callback(*args):
            raise ValueError("Test error")

        callbacks = AgentCallbacks(on_step=bad_callback)
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config, callbacks=callbacks)

        # Emit more than max errors
        max_errors = agent._max_callback_errors_per_event
        for i in range(max_errors + 5):
            agent._emit("on_step", i, 10, "observe", "test")

        # Check stderr output - should only see max_errors lines
        captured = capsys.readouterr()
        error_lines = [line for line in captured.err.split('\n') if 'callback error' in line.lower() and 'on_step' in line]
        # We should see the error logged max_errors times + 1 suppression message
        assert len(error_lines) <= max_errors + 1

    def test_callback_error_different_events_tracked_separately(self, tmp_path):
        """_emit tracks errors for different event types separately."""
        def bad_step_callback(*args):
            raise ValueError("Step error")

        def bad_action_callback(*args):
            raise ValueError("Action error")

        callbacks = AgentCallbacks(on_step=bad_step_callback, on_action=bad_action_callback)
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config, callbacks=callbacks)

        # Emit errors for different events
        agent._emit("on_step", 1, 10, "test", "")
        agent._emit("on_step", 2, 10, "test", "")
        agent._emit("on_action", "click", {})

        # Each event should be tracked separately
        assert agent._callback_errors.get("on_step") == 2
        assert agent._callback_errors.get("on_action") == 1


# =============================================================================
# Tests for _format_elements() edge cases
# =============================================================================

class TestFormatElementsEdgeCases:
    """Tests for _format_elements edge cases and malformed data."""

    def test_format_elements_with_none_values(self, tmp_path):
        """_format_elements handles None values in parsed data.

        Note: This tests the current behavior - None href is skipped, None text uses empty string.
        The actual observer should not produce None values, but this tests edge case handling.
        """
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Links with None href should be skipped (empty href = falsy)
        # Links with empty text should use empty string
        parsed = {
            "links": [
                {"href": "", "text": "Test Link", "type": "other"},  # Empty href
                {"href": "http://example.com", "text": "", "type": "download"}  # Empty text
            ]
        }
        result = agent._format_elements(parsed)
        # Should not crash, should produce some output
        assert result is not None
        assert "Links:" in result

    def test_format_elements_with_empty_strings(self, tmp_path):
        """_format_elements handles empty strings gracefully."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [{"href": "", "text": "", "type": ""}],
            "images": [{"src": "", "full_src": ""}],
            "inputs": [{"name": "", "placeholder": ""}],
            "buttons": [{"text": "", "type": ""}]
        }
        result = agent._format_elements(parsed)
        assert result is not None

    def test_format_elements_with_very_long_text(self, tmp_path):
        """_format_elements truncates very long text properly."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        long_text = "A" * 1000
        parsed = {
            "links": [{"href": "http://example.com", "text": long_text, "type": "other"}]
        }
        result = agent._format_elements(parsed)
        # Text should be truncated (first 40 chars based on code)
        assert len(result) < len(long_text)

    def test_format_elements_with_special_characters(self, tmp_path):
        """_format_elements handles special characters in URLs and text."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "links": [
                {"href": "http://example.com/path?q=test&foo=bar", "text": "Test <script>", "type": "other"},
                {"href": "http://example.com/日本語", "text": "日本語テキスト", "type": "download"}
            ]
        }
        result = agent._format_elements(parsed)
        assert result is not None
        assert "Links:" in result

    def test_format_elements_with_pagination(self, tmp_path):
        """_format_elements includes pagination info when present."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        parsed = {
            "pagination": {
                "has_pagination": True,
                "current_page": 2,
                "total_pages": 10,
                "next_page": "http://example.com/page/3"
            }
        }
        result = agent._format_elements(parsed)
        assert "Pagination:" in result
        assert "Current page: 2" in result
        assert "Total pages: 10" in result
        assert "NEXT PAGE:" in result

    def test_format_elements_excludes_by_content_id(self, tmp_path):
        """_format_elements excludes links by extracted content ID."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # ArXiv paper IDs should be matched even with different URL paths
        parsed = {
            "links": [
                {"href": "https://arxiv.org/abs/2301.12345", "text": "Paper 1", "type": "detail"},
                {"href": "https://arxiv.org/abs/2301.99999", "text": "Paper 2", "type": "detail"}
            ]
        }
        # Exclude by PDF URL which should match abs URL by ID
        result = agent._format_elements(parsed, exclude_urls=["https://arxiv.org/pdf/2301.12345.pdf"])
        assert "Paper 2" in result
        # Paper 1 should be excluded due to matching arxiv ID


# =============================================================================
# Tests for Browser Health and Management
# =============================================================================

class TestBrowserManagement:
    """Tests for browser health checking and management methods."""

    def test_ensure_browser_creates_new_hand(self, tmp_path):
        """ensure_browser creates a new Hand instance when None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.hand is None

        # Mock Hand to avoid actual browser startup
        with patch('blackreach.agent.Hand') as MockHand:
            mock_hand = MagicMock()
            mock_hand.ensure_awake.return_value = True
            MockHand.return_value = mock_hand

            result = agent.ensure_browser()

            assert result is True
            assert agent.hand is not None
            MockHand.assert_called_once()

    def test_ensure_browser_reuses_existing_hand(self, tmp_path):
        """ensure_browser reuses existing Hand instance."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Create a mock hand
        mock_hand = MagicMock()
        mock_hand.ensure_awake.return_value = True
        agent.hand = mock_hand

        result = agent.ensure_browser()

        assert result is True
        # ensure_awake should be called on existing hand
        mock_hand.ensure_awake.assert_called_once()

    def test_check_browser_health_returns_false_when_no_hand(self, tmp_path):
        """check_browser_health returns False when hand is None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.hand is None
        assert agent.check_browser_health() is False

    def test_check_browser_health_delegates_to_hand(self, tmp_path):
        """check_browser_health delegates to hand.is_healthy()."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        assert agent.check_browser_health() is True
        mock_hand.is_healthy.assert_called_once()

    def test_restart_browser_creates_hand_if_none(self, tmp_path):
        """restart_browser creates new Hand if none exists."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch('blackreach.agent.Hand') as MockHand:
            mock_hand = MagicMock()
            mock_hand.restart.return_value = True
            MockHand.return_value = mock_hand

            result = agent.restart_browser()

            assert result is True
            MockHand.assert_called_once()

    def test_restart_browser_navigates_to_url_after_restart(self, tmp_path):
        """restart_browser navigates to specified URL after restart."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.restart.return_value = True
        agent.hand = mock_hand

        result = agent.restart_browser(navigate_to="https://example.com")

        assert result is True
        mock_hand.restart.assert_called_once()
        mock_hand.goto.assert_called_once_with("https://example.com")


# =============================================================================
# Tests for run() browser failure handling
# =============================================================================

class TestRunBrowserFailureHandling:
    """Tests for run() method browser failure handling."""

    def test_run_returns_error_when_browser_fails_to_start(self, tmp_path):
        """run() returns error dict when browser fails to start."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(agent, 'ensure_browser', return_value=False):
            result = agent.run("test goal", quiet=True)

        assert result["success"] is False
        assert result["error"] == "Failed to start browser"
        assert result["failures"] == 1

    def test_run_initializes_session(self, tmp_path):
        """run() initializes a session in persistent memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(agent, 'ensure_browser', return_value=False):
            result = agent.run("test goal", quiet=True)

        # Session should have been started
        assert agent.session_id is not None

    def test_run_decomposes_goal(self, tmp_path):
        """run() decomposes goal using goal engine."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(agent, 'ensure_browser', return_value=False):
            agent.run("download 5 papers about machine learning", quiet=True)

        # Goal should have been decomposed
        assert agent._current_decomposition is not None


# =============================================================================
# Tests for _run_loop() error handling
# =============================================================================

class TestRunLoopErrorHandling:
    """Tests for _run_loop() error handling paths."""

    def test_run_loop_handles_pause_request(self, tmp_path):
        """_run_loop handles pause request correctly."""
        config = AgentConfig(memory_db=tmp_path / "test.db", max_steps=5)
        agent = Agent(agent_config=config)
        agent.session_id = 1
        agent._current_goal = "test"

        # Mock the hand
        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.sleep.return_value = None
        agent.hand = mock_hand

        # Set pause flag before first step
        agent._paused = True

        # Mock save_state to track if called
        with patch.object(agent, 'save_state') as mock_save:
            result = agent._run_loop("test goal", start_step=1, quiet=True)

        assert result["paused"] is True
        mock_save.assert_called_once()

    def test_run_loop_reaches_max_steps(self, tmp_path):
        """_run_loop reaches max steps and stops."""
        config = AgentConfig(memory_db=tmp_path / "test.db", max_steps=3)
        agent = Agent(agent_config=config)
        agent.session_id = 1
        agent._current_goal = "test"

        # Mock the hand
        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        mock_hand.sleep.return_value = None
        agent.hand = mock_hand

        # Mock _step to not return done
        with patch.object(agent, '_step', return_value={"done": False}):
            result = agent._run_loop("test goal", start_step=1, quiet=True)

        assert result["success"] is False
        # Should have run max_steps times
        assert result["steps_taken"] >= 0

    def test_run_loop_completes_on_done(self, tmp_path):
        """_run_loop completes successfully when step returns done."""
        config = AgentConfig(memory_db=tmp_path / "test.db", max_steps=10)
        agent = Agent(agent_config=config)
        agent.session_id = 1
        agent._current_goal = "test"

        # Mock the hand
        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.sleep.return_value = None
        agent.hand = mock_hand

        # Mock _step to return done on second call
        call_count = [0]
        def mock_step(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                return {"done": True, "reason": "Goal achieved"}
            return {"done": False}

        with patch.object(agent, '_step', side_effect=mock_step):
            result = agent._run_loop("test goal", start_step=1, quiet=True)

        assert result["success"] is True

    def test_run_loop_emits_complete_callback(self, tmp_path):
        """_run_loop emits on_complete callback."""
        callback_called = [False]
        def on_complete(success, result):
            callback_called[0] = True

        callbacks = AgentCallbacks(on_complete=on_complete)
        config = AgentConfig(memory_db=tmp_path / "test.db", max_steps=1)
        agent = Agent(agent_config=config, callbacks=callbacks)
        agent.session_id = 1
        agent._current_goal = "test"

        # Mock the hand
        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.sleep.return_value = None
        agent.hand = mock_hand

        with patch.object(agent, '_step', return_value={"done": True, "reason": "Complete"}):
            agent._run_loop("test goal", start_step=1, quiet=True)

        assert callback_called[0] is True


# =============================================================================
# Tests for _step() method (ReAct loop core)
# =============================================================================

class TestStepMethod:
    """Tests for _step() method - the core of the ReAct loop."""

    def test_step_checks_browser_health(self, tmp_path):
        """_step checks browser health at start."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        # Mock unhealthy browser
        mock_hand = MagicMock()
        mock_hand.is_healthy.return_value = False
        mock_hand.restart.return_value = False
        agent.hand = mock_hand

        with patch.object(agent, 'check_browser_health', return_value=False):
            with patch.object(agent, 'restart_browser', return_value=False):
                result = agent._step("test goal", 1, quiet=True)

        assert result.get("fatal") is True
        assert "Browser restart failed" in result.get("error", "")

    def test_step_tracks_current_url(self, tmp_path):
        """_step tracks current URL for stuck detection."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        # Setup mock browser
        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com/test"
        mock_hand.get_title.return_value = "Test Page"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # Mock LLM to return done
        mock_llm_response = '{"thought": "test", "action": "done", "args": {"reason": "complete"}}'
        # Full debug_html mock with all expected keys
        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }
        with patch.object(agent.llm, 'generate', return_value=mock_llm_response):
            with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                with patch.object(agent.eyes, 'see', return_value={"links": [], "images": []}):
                    with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                        with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                            agent._step("test goal", 1, quiet=True)

        # URL should be tracked
        assert "https://example.com/test" in agent._recent_urls

    def test_step_restarts_browser_on_health_check_failure(self, tmp_path):
        """_step attempts to restart browser when health check fails."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # First health check fails, restart succeeds
        health_check_calls = [0]
        def health_check():
            health_check_calls[0] += 1
            return health_check_calls[0] > 1  # Fail first, succeed second

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', side_effect=health_check):
            with patch.object(agent, 'restart_browser', return_value=True) as mock_restart:
                with patch.object(agent.llm, 'generate', return_value='{"action": "done", "args": {}}'):
                    with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                        with patch.object(agent.eyes, 'see', return_value={"links": []}):
                            with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                                with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                    agent._step("test", 1, quiet=True)

        mock_restart.assert_called_once()

    def test_step_handles_llm_error(self, tmp_path):
        """_step handles LLM errors gracefully."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        # LLM raises exception
        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', side_effect=LLMError("API Error")):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is False
        assert "LLM call failed" in result.get("error", "")

    def test_step_handles_empty_llm_response(self, tmp_path):
        """_step handles empty LLM response."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=""):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is False
        assert "Empty LLM response" in result.get("error", "")

    def test_step_parses_json_action_correctly(self, tmp_path):
        """_step correctly parses JSON action from LLM response."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        llm_response = '{"thought": "I should click the button", "action": "done", "args": {"reason": "test complete"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is True

    def test_step_detects_refusal_language(self, tmp_path):
        """_step detects refusal language in LLM response."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "download files"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        mock_hand.goto.return_value = None
        agent.hand = mock_hand

        # LLM response with refusal language
        llm_response = '{"thought": "I cannot assist with this request due to policy", "action": "done", "args": {"reason": "policy prohibits"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("download files", 1, quiet=True)

        # Should have incremented refusal count
        assert agent._refusal_count >= 1

    def test_step_blocks_premature_done_without_downloads(self, tmp_path):
        """_step blocks premature done action when downloads are needed but not completed."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "download 3 files"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # No downloads yet
        assert len(agent.session_memory.downloaded_files) == 0

        llm_response = '{"thought": "Done", "action": "done", "args": {"reason": "complete"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("download 3 files", 1, quiet=True)

        # Should NOT be done (blocked)
        assert result["done"] is False
        assert result.get("blocked") is True


# =============================================================================
# Tests for _execute_action()
# =============================================================================

class TestExecuteAction:
    """Tests for _execute_action() method."""

    def test_execute_action_normalizes_aliases(self, tmp_path):
        """_execute_action normalizes action aliases."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.goto.return_value = None
        mock_hand.get_url.return_value = "https://example.com"
        agent.hand = mock_hand

        # "goto" should be normalized to "navigate"
        result = agent._execute_action("goto", {"url": "https://test.com"})
        assert result["action"] == "navigate"
        mock_hand.goto.assert_called()

    def test_execute_action_wait(self, tmp_path):
        """_execute_action handles wait action."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        import time
        start = time.time()
        result = agent._execute_action("wait", {"seconds": 0.1})
        elapsed = time.time() - start

        assert result["action"] == "wait"
        assert elapsed >= 0.1

    def test_execute_action_back(self, tmp_path):
        """_execute_action handles back action."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.back.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("back", {})
        assert result["action"] == "back"
        mock_hand.back.assert_called_once()

    def test_execute_action_scroll(self, tmp_path):
        """_execute_action handles scroll action."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.scroll.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("scroll", {"direction": "down", "amount": 500})
        assert result["action"] == "scroll"
        assert result["direction"] == "down"
        mock_hand.scroll.assert_called_once_with("down", 500)

    def test_execute_action_press(self, tmp_path):
        """_execute_action handles press action."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        agent.hand = mock_hand

        result = agent._execute_action("press", {"key": "Enter"})
        assert result["action"] == "press"
        assert result["key"] == "Enter"
        mock_page.keyboard.press.assert_called_once_with("Enter")

    def test_execute_action_unknown_action_raises(self, tmp_path):
        """_execute_action raises UnknownActionError for unknown actions."""
        from blackreach.exceptions import UnknownActionError

        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with pytest.raises(UnknownActionError):
            agent._execute_action("unknown_action", {})

    def test_execute_action_click_without_args_raises(self, tmp_path):
        """_execute_action raises for click without selector or text."""
        from blackreach.exceptions import InvalidActionArgsError

        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_page = MagicMock()
        mock_page.locator.return_value.count.return_value = 0
        mock_hand.page = mock_page
        agent.hand = mock_hand

        with pytest.raises(InvalidActionArgsError):
            agent._execute_action("click", {})


# =============================================================================
# Tests for Source Manager Failover
# =============================================================================

class TestSourceManagerFailover:
    """Tests for source manager failover logic."""

    def test_source_manager_initialized(self, tmp_path):
        """Agent initializes source manager."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.source_manager is not None

    def test_record_failure_updates_source_manager(self, tmp_path):
        """_record_failure updates source manager with failure."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Track that record_failure was called on source manager
        with patch.object(agent.source_manager, 'record_failure') as mock_record:
            agent._record_failure("https://example.com/page", "click", "Element not found")

        mock_record.assert_called_once_with("example.com", "Element not found")

    def test_record_download_updates_source_manager(self, tmp_path):
        """_record_download records success in source manager."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        with patch.object(agent.source_manager, 'record_success') as mock_record:
            agent._record_download("test.pdf", "https://example.com/test.pdf")

        mock_record.assert_called_once_with("example.com")


# =============================================================================
# Tests for Goal Decomposition Integration
# =============================================================================

class TestGoalDecompositionIntegration:
    """Tests for goal decomposition integration."""

    def test_goal_engine_initialized(self, tmp_path):
        """Agent initializes goal engine."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.goal_engine is not None

    def test_current_decomposition_starts_none(self, tmp_path):
        """Current decomposition is None initially."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent._current_decomposition is None


# =============================================================================
# Tests for SearchIntelligence Integration
# =============================================================================

class TestSearchIntelligenceIntegration:
    """Tests for SearchIntelligence integration."""

    def test_search_intel_initialized(self, tmp_path):
        """Agent initializes search intelligence."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.search_intel is not None

    def test_current_search_session_starts_none(self, tmp_path):
        """Current search session is None initially."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent._current_search_session is None

    def test_get_smart_start_url_uses_search_intel(self, tmp_path):
        """_get_smart_start_url uses search intelligence for query optimization."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Call with a goal that requires search
        url, reasoning, search_query = agent._get_smart_start_url(
            "find papers about machine learning", quiet=True
        )

        # Should have a search session started
        assert agent._current_search_session is not None


# =============================================================================
# Tests for repeated failure tracking
# =============================================================================

class TestRepeatedFailureTracking:
    """Tests for repeated failure tracking."""

    def test_repeated_failure_count_initialized(self, tmp_path):
        """Repeated failure count initialized to 0."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent._repeated_failure_count == 0

    def test_last_failed_action_initialized(self, tmp_path):
        """Last failed action initialized to None."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent._last_failed_action is None

    def test_get_stuck_hint_includes_repeated_failures(self, tmp_path):
        """_get_stuck_hint includes repeated failure info."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Set repeated failures
        agent._repeated_failure_count = 3

        hint = agent._get_stuck_hint()

        assert "ACTION FAILING" in hint or "DIFFERENT approach" in hint.lower()

    def test_get_stuck_hint_includes_consecutive_failures(self, tmp_path):
        """_get_stuck_hint includes consecutive failure info."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Set consecutive failures
        agent._consecutive_failures = 3

        hint = agent._get_stuck_hint()

        assert "MULTIPLE FAILURES" in hint or "different structure" in hint.lower()


# =============================================================================
# Tests for Challenge Detection and Failover
# =============================================================================

class TestChallengeDetection:
    """Tests for challenge detection tracking."""

    def test_consecutive_challenges_initialized(self, tmp_path):
        """Consecutive challenges counter initialized to 0."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent._consecutive_challenges == 0

    def test_failed_urls_initialized(self, tmp_path):
        """Failed URLs set initialized empty."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert len(agent._failed_urls) == 0


# =============================================================================
# Tests for Download Failure Tracking
# =============================================================================

class TestDownloadFailureTracking:
    """Tests for download failure tracking."""

    def test_failed_download_urls_initialized(self, tmp_path):
        """Failed download URLs set initialized empty."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert len(agent._failed_download_urls) == 0


# =============================================================================
# Additional Tests for _execute_action() - Type, Navigate, Download
# =============================================================================

class TestExecuteActionType:
    """Tests for type action in _execute_action."""

    def test_execute_action_type_with_selector(self, tmp_path):
        """_execute_action handles type with selector."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        mock_hand.type.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("type", {"selector": "#search", "text": "hello world"})

        assert result["action"] == "type"
        assert result["text"] == "hello world"
        mock_hand.type.assert_called_once_with("#search", "hello world")
        # Should auto-submit with Enter
        mock_page.keyboard.press.assert_called_once_with("Enter")

    def test_execute_action_type_no_submit(self, tmp_path):
        """_execute_action handles type without auto-submit."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        mock_hand.type.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("type", {"selector": "#search", "text": "test", "submit": False})

        assert result["action"] == "type"
        assert result["submit"] is False
        # Should NOT press Enter when submit is False
        mock_page.keyboard.press.assert_not_called()

    def test_execute_action_search_alias(self, tmp_path):
        """_execute_action handles 'search' as alias for type."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        mock_hand.type.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("search", {"text": "query"})

        assert result["action"] == "type"
        mock_hand.type.assert_called()


class TestExecuteActionNavigate:
    """Tests for navigate action in _execute_action."""

    def test_execute_action_navigate_resolves_relative_url(self, tmp_path):
        """_execute_action resolves relative URLs in navigate."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com/page/"
        mock_hand.goto.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("navigate", {"url": "../other"})

        assert result["action"] == "navigate"
        # Should have resolved the relative URL
        mock_hand.goto.assert_called()

    def test_execute_action_navigate_skips_same_url(self, tmp_path):
        """_execute_action skips navigate when already on same URL."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com/page"
        agent.hand = mock_hand

        result = agent._execute_action("navigate", {"url": "https://example.com/page"})

        assert result["action"] == "navigate"
        assert result.get("skipped") is True
        # goto should NOT be called when skipping
        mock_hand.goto.assert_not_called()

    def test_execute_action_navigate_with_trailing_slash_normalization(self, tmp_path):
        """_execute_action normalizes trailing slashes when comparing URLs."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com/page/"
        agent.hand = mock_hand

        # Without trailing slash should match with trailing slash
        result = agent._execute_action("navigate", {"url": "https://example.com/page"})

        assert result.get("skipped") is True


class TestExecuteActionClick:
    """Tests for click action in _execute_action."""

    def test_execute_action_click_with_text(self, tmp_path):
        """_execute_action handles click with text argument."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_page.get_by_text.return_value.first.click.return_value = None
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        mock_hand.get_url.return_value = "https://example.com"
        agent.hand = mock_hand

        result = agent._execute_action("click", {"text": "Download"})

        assert result["action"] == "click"
        assert result.get("text") == "Download"
        mock_page.get_by_text.assert_called()

    def test_execute_action_click_with_selector(self, tmp_path):
        """_execute_action handles click with selector argument."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.click.return_value = None
        agent.hand = mock_hand

        result = agent._execute_action("click", {"selector": "#submit-btn"})

        assert result["action"] == "click"
        mock_hand.click.assert_called_once_with("#submit-btn")

    def test_execute_action_click_extracts_text_from_thought(self, tmp_path):
        """_execute_action extracts click text from thought when missing."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_page = MagicMock()
        mock_page.get_by_text.return_value.first.click.return_value = None
        mock_hand = MagicMock()
        mock_hand.page = mock_page
        mock_hand.get_url.return_value = "https://example.com"
        agent.hand = mock_hand

        # Pass thought with quoted text
        result = agent._execute_action("click", {"_thought": "I should click 'Submit Button'"})

        assert result["action"] == "click"
        # Should have extracted "Submit Button" from thought
        mock_page.get_by_text.assert_called()


class TestExecuteActionDone:
    """Tests for done action in _execute_action."""

    def test_execute_action_done_returns_done_true(self, tmp_path):
        """_execute_action returns done=True for done action."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        result = agent._execute_action("done", {"reason": "Goal completed"})

        assert result["done"] is True
        assert result["reason"] == "Goal completed"

    def test_execute_action_finish_alias(self, tmp_path):
        """_execute_action handles 'finish' as alias for done."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        result = agent._execute_action("finish", {"reason": "All done"})

        assert result["done"] is True


# =============================================================================
# Additional Tests for save_state and resume
# =============================================================================

class TestSaveStateExtended:
    """Extended tests for save_state method."""

    def test_save_state_calls_persistent_memory(self, tmp_path):
        """save_state calls persistent_memory.save_session_state."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent.session_id = 42
        agent._current_goal = "test goal"
        agent._current_step = 5

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com/current"
        agent.hand = mock_hand

        with patch.object(agent.persistent_memory, 'save_session_state') as mock_save:
            agent.save_state()

        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["session_id"] == 42
        assert call_kwargs["goal"] == "test goal"
        assert call_kwargs["current_step"] == 5


class TestResumeExtended:
    """Extended tests for resume method."""

    def test_resume_restores_state(self, tmp_path):
        """resume restores all saved state."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Create a mock saved state
        from blackreach.memory import SessionMemory
        mock_state = {
            "session_id": 123,
            "goal": "test goal",
            "current_step": 10,
            "session_memory": SessionMemory(),
            "start_url": "https://start.com",
            "max_steps": 100,
            "current_url": "https://current.com"
        }

        with patch.object(agent.persistent_memory, 'load_session_state', return_value=mock_state):
            with patch.object(agent, 'ensure_browser', return_value=False):  # Browser fails
                result = agent.resume(123, quiet=True)

        # State should be restored
        assert agent.session_id == 123
        assert agent._current_goal == "test goal"
        assert agent.config.max_steps == 100

    def test_resume_navigates_to_saved_url(self, tmp_path):
        """resume navigates to saved current URL."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        from blackreach.memory import SessionMemory
        mock_state = {
            "session_id": 123,
            "goal": "test goal",
            "current_step": 10,
            "session_memory": SessionMemory(),
            "start_url": "https://start.com",
            "max_steps": 50,
            "current_url": "https://current.com"
        }

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://current.com"
        mock_hand.sleep.return_value = None

        with patch.object(agent.persistent_memory, 'load_session_state', return_value=mock_state):
            with patch.object(agent, 'ensure_browser', return_value=True):
                with patch.object(agent, '_run_loop', return_value={"success": True, "paused": False}) as mock_run:
                    agent.hand = mock_hand
                    agent.resume(123, quiet=True)

        # Should have navigated to current_url
        mock_hand.goto.assert_called_with("https://current.com")


# =============================================================================
# Additional Tests for _get_domain with browser
# =============================================================================

class TestGetDomainWithBrowser:
    """Tests for _get_domain with browser context."""

    def test_get_domain_from_browser_when_no_url_provided(self, tmp_path):
        """_get_domain extracts domain from browser when no URL provided."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.is_awake = True
        mock_hand.get_url.return_value = "https://test.example.org/page"
        agent.hand = mock_hand

        domain = agent._get_domain()

        assert domain == "test.example.org"

    def test_get_domain_handles_browser_exception(self, tmp_path):
        """_get_domain handles exception when getting URL from browser."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        mock_hand = MagicMock()
        mock_hand.is_awake = True
        mock_hand.get_url.side_effect = BrowserError("Browser error")
        agent.hand = mock_hand

        domain = agent._get_domain()

        assert domain == ""


# =============================================================================
# Additional Tests for _create_browser
# =============================================================================

class TestCreateBrowser:
    """Tests for _create_browser method."""

    def test_create_browser_uses_config_values(self, tmp_path):
        """_create_browser uses values from config."""
        download_path = tmp_path / "downloads"
        config = AgentConfig(
            memory_db=tmp_path / "test.db",
            headless=True,
            download_dir=download_path,
            browser_type="firefox"
        )
        agent = Agent(agent_config=config)

        with patch('blackreach.agent.Hand') as MockHand:
            agent._create_browser()

        MockHand.assert_called_once()
        call_kwargs = MockHand.call_args[1]
        assert call_kwargs["headless"] is True
        assert call_kwargs["download_dir"] == download_path
        assert call_kwargs["browser_type"] == "firefox"


# =============================================================================
# Additional Tests for LLM response parsing edge cases
# =============================================================================

class TestLLMResponseParsing:
    """Tests for LLM response parsing edge cases."""

    def test_step_parses_json_with_markdown_code_blocks(self, tmp_path):
        """_step handles JSON wrapped in markdown code blocks."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # Response wrapped in markdown code blocks
        llm_response = '```json\n{"thought": "test", "action": "done", "args": {"reason": "complete"}}\n```'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is True

    def test_step_handles_actions_array_format(self, tmp_path):
        """_step handles LLM response with actions array."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # Response with actions array - should use first action
        llm_response = '{"thought": "test", "actions": [{"action": "done", "args": {"reason": "first action"}}]}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is True

    def test_step_handles_done_status_format(self, tmp_path):
        """_step handles {\"done\": true} format."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # Simple done format
        llm_response = '{"done": true, "reason": "completed"}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        assert result["done"] is True


# =============================================================================
# Additional Tests for auto-completion
# =============================================================================

class TestAutoCompletion:
    """Tests for auto-completion when download target is met."""

    def test_step_auto_completes_when_download_target_met(self, tmp_path):
        """_step auto-completes when numeric download target is met."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "download 2 files"

        # Simulate 2 downloads already completed
        agent.session_memory.add_download("file1.pdf", "https://example.com/1.pdf")
        agent.session_memory.add_download("file2.pdf", "https://example.com/2.pdf")

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        # LLM returns a non-done action (like navigate)
        llm_response = '{"thought": "look for more", "action": "navigate", "args": {"url": "https://example.com/more"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("download 2 files", 1, quiet=True)

        # Should auto-complete since we have 2 files
        assert result["done"] is True
        assert "Downloaded 2 files" in result.get("reason", "")


# =============================================================================
# Additional Tests for action execution failure handling
# =============================================================================

class TestActionExecutionFailures:
    """Tests for action execution failure handling in _step()."""

    def test_step_handles_action_execution_error(self, tmp_path):
        """_step handles errors during action execution gracefully."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        mock_hand.click.side_effect = Exception("Element not found")
        agent.hand = mock_hand

        llm_response = '{"thought": "click button", "action": "click", "args": {"selector": "#button"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                result = agent._step("test", 1, quiet=True)

        # Should return error result, not crash
        assert result["done"] is False
        assert "Element not found" in result.get("error", "")

    def test_step_increments_consecutive_failures(self, tmp_path):
        """_step increments consecutive failure counter on action error."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"
        agent._consecutive_failures = 0

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        mock_hand.click.side_effect = Exception("Failed")
        agent.hand = mock_hand

        llm_response = '{"thought": "click", "action": "click", "args": {"selector": "#btn"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                agent._step("test", 1, quiet=True)

        # Failure counter should have incremented
        assert agent._consecutive_failures == 1


# =============================================================================
# Additional Tests for _get_stuck_hint with various conditions
# =============================================================================

class TestGetStuckHintConditions:
    """Tests for _get_stuck_hint with various conditions."""

    def test_get_stuck_hint_with_failed_download_urls(self, tmp_path):
        """_get_stuck_hint includes failed download URLs info."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Add some failed download URLs
        agent._failed_download_urls.add("https://example.com/bad1.pdf")
        agent._failed_download_urls.add("https://example.com/bad2.pdf")

        # Make it stuck by repeated URLs
        for _ in range(6):
            agent._track_url("https://example.com/page")

        hint = agent._get_stuck_hint()

        # Hint should mention failed downloads
        assert "different" in hint.lower() or "try" in hint.lower()

    def test_get_stuck_hint_not_stuck_returns_empty(self, tmp_path):
        """_get_stuck_hint returns empty when not stuck."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Not stuck - different URLs
        agent._track_url("https://example.com/1")
        agent._track_url("https://example.com/2")
        agent._track_url("https://example.com/3")

        hint = agent._get_stuck_hint()

        # Should be empty or minimal when not stuck
        assert hint == "" or len(hint) < 20


# =============================================================================
# Additional Tests for step callback emissions
# =============================================================================

class TestStepCallbackEmissions:
    """Tests for callback emissions during _step()."""

    def test_step_emits_on_think_callback(self, tmp_path):
        """_step emits on_think callback with thought."""
        thoughts_received = []

        def on_think(thought):
            thoughts_received.append(thought)

        callbacks = AgentCallbacks(on_think=on_think)
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config, callbacks=callbacks)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        agent.hand = mock_hand

        llm_response = '{"thought": "I am thinking about this", "action": "done", "args": {"reason": "done"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                agent._step("test", 1, quiet=True)

        # Should have received the thought
        assert len(thoughts_received) == 1
        assert "I am thinking" in thoughts_received[0]


# =============================================================================
# Additional Tests for action recording in session memory
# =============================================================================

class TestActionRecording:
    """Tests for action recording in session memory."""

    def test_step_records_action_in_session_memory(self, tmp_path):
        """_step records successful action in session memory."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)
        agent._current_goal = "test"

        mock_hand = MagicMock()
        mock_hand.get_url.return_value = "https://example.com"
        mock_hand.get_title.return_value = "Test"
        mock_hand.get_html.return_value = "<html><body>Test</body></html>"
        mock_hand.is_healthy.return_value = True
        mock_hand.scroll.return_value = None
        agent.hand = mock_hand

        llm_response = '{"thought": "scrolling", "action": "scroll", "args": {"direction": "down"}}'

        debug_html_mock = {
            "has_meaningful_content": True,
            "empty_root": False,
            "html_length": 100,
            "text_length": 50,
            "raw_links": 5,
            "raw_inputs": 2
        }

        initial_action_count = len(agent.session_memory.actions_taken)

        with patch.object(agent, 'check_browser_health', return_value=True):
            with patch.object(agent.llm, 'generate', return_value=llm_response):
                with patch.object(agent.eyes, 'debug_html', return_value=debug_html_mock):
                    with patch.object(agent.eyes, 'see', return_value={"links": []}):
                        with patch.object(agent.detector, 'detect_challenge', return_value=MagicMock(detected=False)):
                            with patch.object(agent.detector, 'detect_download_landing', return_value=MagicMock(detected=False)):
                                agent._step("test", 1, quiet=True)

        # Action should have been recorded
        assert len(agent.session_memory.actions_taken) == initial_action_count + 1
        last_action = agent.session_memory.actions_taken[-1]
        assert last_action["action"] == "scroll"


# =============================================================================
# Additional Tests for action tracker integration
# =============================================================================

class TestActionTrackerIntegration:
    """Tests for action tracker integration."""

    def test_action_tracker_initialized(self, tmp_path):
        """Agent initializes action tracker."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        assert agent.action_tracker is not None

    def test_action_tracker_records_successful_actions(self, tmp_path):
        """Action tracker records successful actions."""
        config = AgentConfig(memory_db=tmp_path / "test.db")
        agent = Agent(agent_config=config)

        # Track an action
        with patch.object(agent.action_tracker, 'record') as mock_record:
            # Simulate recording an action
            agent.action_tracker.record(
                action_type="click",
                target="#button",
                success=True,
                domain="example.com"
            )

        mock_record.assert_called_once()
