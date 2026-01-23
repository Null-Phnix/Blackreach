"""
Unit tests for blackreach/llm.py

Tests LLM configuration, response parsing, and action extraction.
Does NOT test actual LLM API calls (those require mocking or integration tests).
"""

import pytest
from blackreach.llm import LLM, LLMConfig, LLMResponse
from blackreach.exceptions import ProviderError, ProviderNotInstalledError


# =============================================================================
# LLMConfig Tests
# =============================================================================

class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = LLMConfig()

        assert config.provider == "ollama"
        assert config.model == "qwen2.5:7b"
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.api_key is None
        assert config.api_base is None

    def test_custom_values(self):
        """Config accepts custom values."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            temperature=0.5,
            max_tokens=2048
        )

        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


# =============================================================================
# LLMResponse Tests
# =============================================================================

class TestLLMResponse:
    """Tests for LLM response dataclass."""

    def test_basic_response(self):
        """Can create basic response."""
        response = LLMResponse(
            thought="I should click the button",
            action="click",
            args={"selector": "#btn"},
            done=False
        )

        assert response.thought == "I should click the button"
        assert response.action == "click"
        assert response.args == {"selector": "#btn"}
        assert response.done is False

    def test_is_valid_with_action(self):
        """Response is valid if it has an action."""
        response = LLMResponse(
            thought="test",
            action="click",
            args={},
            done=False
        )
        assert response.is_valid is True

    def test_is_valid_when_done(self):
        """Response is valid if done is True."""
        response = LLMResponse(
            thought="test",
            action=None,
            args={},
            done=True
        )
        assert response.is_valid is True

    def test_is_invalid_no_action_not_done(self):
        """Response is invalid if no action and not done."""
        response = LLMResponse(
            thought="test",
            action=None,
            args={},
            done=False
        )
        assert response.is_valid is False

    def test_reason_field(self):
        """Response can have reason field."""
        response = LLMResponse(
            thought="test",
            action="done",
            args={},
            done=True,
            reason="Downloaded all files"
        )
        assert response.reason == "Downloaded all files"

    def test_raw_response_field(self):
        """Response stores raw response text."""
        raw = '{"action": "click"}'
        response = LLMResponse(
            thought="test",
            action="click",
            args={},
            done=False,
            raw_response=raw
        )
        assert response.raw_response == raw


# =============================================================================
# parse_action Tests
# =============================================================================

class TestParseAction:
    """Tests for LLM.parse_action() method."""

    @pytest.fixture
    def llm(self):
        """Create LLM instance for testing parse_action.

        Note: This may fail if ollama is not installed, but parse_action
        doesn't require a connection, so we can still test it.
        """
        try:
            return LLM(LLMConfig())
        except (ImportError, ProviderNotInstalledError):
            pytest.skip("ollama not installed")

    def test_parse_simple_action(self, llm):
        """Parse simple action JSON."""
        response = '{"thought": "I see a button", "action": "click", "args": {"selector": "#btn"}}'
        result = llm.parse_action(response)

        assert result.thought == "I see a button"
        assert result.action == "click"
        assert result.args == {"selector": "#btn"}
        assert result.done is False

    def test_parse_navigate_action(self, llm):
        """Parse navigate action."""
        response = '{"thought": "Going to search page", "action": "navigate", "args": {"url": "https://arxiv.org"}}'
        result = llm.parse_action(response)

        assert result.action == "navigate"
        assert result.args["url"] == "https://arxiv.org"

    def test_parse_download_action(self, llm):
        """Parse download action."""
        response = '{"thought": "Found PDF", "action": "download", "args": {"url": "https://arxiv.org/pdf/123.pdf"}}'
        result = llm.parse_action(response)

        assert result.action == "download"
        assert "pdf" in result.args["url"]

    def test_parse_type_action(self, llm):
        """Parse type action."""
        response = '{"thought": "Entering search", "action": "type", "args": {"selector": "#search", "text": "machine learning"}}'
        result = llm.parse_action(response)

        assert result.action == "type"
        assert result.args["selector"] == "#search"
        assert result.args["text"] == "machine learning"

    def test_parse_done_action(self, llm):
        """Parse done action sets done=True."""
        response = '{"thought": "All done", "action": "done", "args": {"reason": "Downloaded 5 papers"}}'
        result = llm.parse_action(response)

        assert result.action == "done"
        assert result.done is True
        assert result.reason == "Downloaded 5 papers"

    def test_parse_done_flag(self, llm):
        """Parse done flag without action."""
        response = '{"thought": "Finished", "done": true, "reason": "Task complete"}'
        result = llm.parse_action(response)

        assert result.done is True
        assert result.reason == "Task complete"

    def test_parse_markdown_wrapped(self, llm):
        """Parse JSON wrapped in markdown code block."""
        response = '''```json
        {"thought": "test", "action": "click", "args": {"selector": "#btn"}}
        ```'''
        result = llm.parse_action(response)

        assert result.action == "click"

    def test_parse_triple_backticks(self, llm):
        """Parse JSON wrapped in plain backticks."""
        response = '''```
        {"thought": "test", "action": "navigate", "args": {"url": "https://example.com"}}
        ```'''
        result = llm.parse_action(response)

        assert result.action == "navigate"

    def test_parse_json_with_surrounding_text(self, llm):
        """Parse JSON embedded in text."""
        response = '''I think we should navigate to the page.
        {"thought": "navigating", "action": "navigate", "args": {"url": "https://example.com"}}
        That's my plan.'''
        result = llm.parse_action(response)

        assert result.action == "navigate"

    def test_parse_multiline_json(self, llm):
        """Parse multi-line formatted JSON."""
        response = '''{
            "thought": "I found the download button",
            "action": "click",
            "args": {
                "selector": "#download-btn"
            }
        }'''
        result = llm.parse_action(response)

        assert result.action == "click"
        assert result.args["selector"] == "#download-btn"

    def test_parse_no_json_returns_invalid(self, llm):
        """No JSON in response returns invalid result."""
        response = "I don't know what to do next."
        result = llm.parse_action(response)

        assert result.action is None
        assert result.is_valid is False
        assert "no JSON found" in result.thought

    def test_parse_invalid_json_returns_error(self, llm):
        """Invalid JSON returns error result."""
        response = '{"thought": "test", "action": click}'  # Missing quotes
        result = llm.parse_action(response)

        assert result.action is None
        assert result.is_valid is False
        assert "parse error" in result.thought.lower()

    def test_parse_empty_response(self, llm):
        """Empty response returns invalid result."""
        result = llm.parse_action("")

        assert result.action is None
        assert result.is_valid is False

    def test_parse_preserves_raw_response(self, llm):
        """Raw response is preserved in result."""
        response = '{"thought": "test", "action": "click", "args": {}}'
        result = llm.parse_action(response)

        assert result.raw_response == response

    def test_parse_missing_thought(self, llm):
        """Missing thought field defaults to empty string."""
        response = '{"action": "click", "args": {"selector": "#btn"}}'
        result = llm.parse_action(response)

        assert result.thought == ""
        assert result.action == "click"

    def test_parse_missing_args(self, llm):
        """Missing args field defaults to empty dict."""
        response = '{"thought": "test", "action": "scroll"}'
        result = llm.parse_action(response)

        assert result.args == {}

    def test_parse_nested_json_in_args(self, llm):
        """Complex nested args are preserved."""
        response = '''{"thought": "test", "action": "custom", "args": {"data": {"nested": true, "list": [1, 2, 3]}}}'''
        result = llm.parse_action(response)

        assert result.args["data"]["nested"] is True
        assert result.args["data"]["list"] == [1, 2, 3]

    def test_parse_unicode_content(self, llm):
        """Unicode content in JSON is handled."""
        response = '{"thought": "日本語", "action": "click", "args": {"text": "検索"}}'
        result = llm.parse_action(response)

        assert result.thought == "日本語"
        assert result.args["text"] == "検索"

    def test_parse_action_done_with_reason_in_args(self, llm):
        """Done action extracts reason from args."""
        response = '{"thought": "finished", "action": "done", "args": {"reason": "All papers downloaded"}}'
        result = llm.parse_action(response)

        assert result.done is True
        assert result.reason == "All papers downloaded"

    def test_parse_action_done_with_top_level_reason(self, llm):
        """Done action uses top-level reason if present."""
        response = '{"thought": "finished", "action": "done", "reason": "Top level reason", "args": {}}'
        result = llm.parse_action(response)

        assert result.done is True
        assert result.reason == "Top level reason"


# =============================================================================
# LLM Initialization Tests (without actual API calls)
# =============================================================================

class TestLLMInitialization:
    """Tests for LLM class initialization."""

    def test_unsupported_provider_raises(self):
        """Unsupported provider raises ProviderError."""
        config = LLMConfig(provider="unsupported_provider")

        with pytest.raises(ProviderError) as exc_info:
            LLM(config)

        assert "unsupported_provider" in str(exc_info.value)

    def test_ollama_provider_type(self):
        """Ollama provider sets correct type."""
        try:
            llm = LLM(LLMConfig(provider="ollama"))
            assert llm._provider_type == "ollama"
        except (ImportError, ProviderNotInstalledError):
            pytest.skip("ollama not installed")

    def test_config_stored(self):
        """Config is stored on LLM instance."""
        try:
            config = LLMConfig(model="test-model", temperature=0.5)
            llm = LLM(config)
            assert llm.config.model == "test-model"
            assert llm.config.temperature == 0.5
        except (ImportError, ProviderNotInstalledError):
            pytest.skip("ollama not installed")
