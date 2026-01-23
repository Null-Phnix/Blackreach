"""
Unit tests for blackreach/llm.py

Tests LLM configuration and response parsing.
Note: Provider integration tests require actual API keys.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from blackreach.llm import LLM, LLMConfig, LLMResponse
from blackreach.exceptions import ProviderError, ProviderNotInstalledError


class TestLLMConfig:
    """Tests for LLMConfig defaults."""

    def test_default_provider(self):
        """LLMConfig defaults to ollama provider."""
        config = LLMConfig()
        assert config.provider == "ollama"

    def test_default_model(self):
        """LLMConfig has default model."""
        config = LLMConfig()
        assert config.model == "qwen2.5:7b"

    def test_default_api_key(self):
        """LLMConfig defaults to no API key."""
        config = LLMConfig()
        assert config.api_key is None

    def test_default_temperature(self):
        """LLMConfig has default temperature."""
        config = LLMConfig()
        assert config.temperature == 0.7

    def test_default_max_tokens(self):
        """LLMConfig has default max_tokens."""
        config = LLMConfig()
        assert config.max_tokens == 1024

    def test_default_max_retries(self):
        """LLMConfig has default max_retries."""
        config = LLMConfig()
        assert config.max_retries == 3

    def test_default_retry_delay(self):
        """LLMConfig has default retry_delay."""
        config = LLMConfig()
        assert config.retry_delay == 1.0

    def test_custom_provider(self):
        """LLMConfig accepts custom provider."""
        config = LLMConfig(provider="openai")
        assert config.provider == "openai"

    def test_custom_model(self):
        """LLMConfig accepts custom model."""
        config = LLMConfig(model="gpt-4")
        assert config.model == "gpt-4"

    def test_custom_api_key(self):
        """LLMConfig accepts custom API key."""
        config = LLMConfig(api_key="test-key")
        assert config.api_key == "test-key"

    def test_custom_temperature(self):
        """LLMConfig accepts custom temperature."""
        config = LLMConfig(temperature=0.5)
        assert config.temperature == 0.5


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_valid_with_action(self):
        """LLMResponse is valid with action."""
        response = LLMResponse(
            thought="test thought",
            action="click",
            args={"selector": "button"},
            done=False
        )
        assert response.is_valid is True

    def test_valid_when_done(self):
        """LLMResponse is valid when done."""
        response = LLMResponse(
            thought="finished",
            action=None,
            args={},
            done=True
        )
        assert response.is_valid is True

    def test_invalid_without_action_or_done(self):
        """LLMResponse is invalid without action or done."""
        response = LLMResponse(
            thought="confused",
            action=None,
            args={},
            done=False
        )
        assert response.is_valid is False

    def test_reason_attribute(self):
        """LLMResponse stores reason."""
        response = LLMResponse(
            thought="done",
            action=None,
            args={},
            done=True,
            reason="Goal achieved"
        )
        assert response.reason == "Goal achieved"

    def test_raw_response_attribute(self):
        """LLMResponse stores raw response."""
        response = LLMResponse(
            thought="test",
            action="click",
            args={},
            done=False,
            raw_response='{"action": "click"}'
        )
        assert response.raw_response == '{"action": "click"}'


class TestLLMParseAction:
    """Tests for parse_action method."""

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_simple_json(self, mock_init):
        """parse_action handles simple JSON."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('{"action": "click", "args": {"selector": "button"}}')

        assert result.action == "click"
        assert result.args == {"selector": "button"}

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_with_thought(self, mock_init):
        """parse_action extracts thought."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('{"thought": "I should click the button", "action": "click", "args": {}}')

        assert result.thought == "I should click the button"

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_done_action(self, mock_init):
        """parse_action handles done action."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('{"action": "done", "reason": "Goal complete"}')

        assert result.done is True
        assert result.reason == "Goal complete"

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_done_flag(self, mock_init):
        """parse_action handles done flag."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('{"done": true, "reason": "All done"}')

        assert result.done is True

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_strips_markdown(self, mock_init):
        """parse_action strips markdown code blocks."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('```json\n{"action": "click"}\n```')

        assert result.action == "click"

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_no_json(self, mock_init):
        """parse_action handles missing JSON."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action("I don't know what to do")

        assert result.action is None
        assert "no json found" in result.thought.lower()

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_invalid_json(self, mock_init):
        """parse_action handles invalid JSON."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('{"action": "click", invalid}')

        assert result.action is None
        assert "parse error" in result.thought.lower()

    @patch('blackreach.llm.LLM._init_client')
    def test_parse_stores_raw_response(self, mock_init):
        """parse_action stores raw response."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        original = '{"action": "click"}'
        result = llm.parse_action(original)

        assert result.raw_response == original


class TestLLMProviderError:
    """Tests for provider error handling."""

    def test_unsupported_provider_raises(self):
        """Unsupported provider raises ProviderError."""
        config = LLMConfig(provider="invalid_provider")

        with pytest.raises(ProviderError):
            # Create instance without using the mock - call real _init_client
            llm = LLM.__new__(LLM)
            llm.config = config
            llm._client = None
            llm._provider_type = None
            # Call the real init_client method directly
            LLM._init_client(llm)


class TestLLMGenerate:
    """Tests for generate method retry logic."""

    @patch('blackreach.llm.LLM._init_client')
    @patch('time.sleep')
    def test_generate_retries_on_failure(self, mock_sleep, mock_init):
        """generate retries on failure."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=3, retry_delay=0.1)
        llm._client = None
        llm._provider_type = "ollama"

        # Mock the provider call to fail twice then succeed
        call_count = [0]

        def mock_call_ollama(system, user):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary error")
            return "success"

        llm._call_ollama = mock_call_ollama

        result = llm.generate("system", "user")

        assert result == "success"
        assert call_count[0] == 3

    @patch('blackreach.llm.LLM._init_client')
    @patch('time.sleep')
    def test_generate_raises_after_max_retries(self, mock_sleep, mock_init):
        """generate raises after max retries."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=2, retry_delay=0.1)
        llm._client = None
        llm._provider_type = "ollama"

        def mock_call_ollama(system, user):
            raise Exception("Persistent error")

        llm._call_ollama = mock_call_ollama

        with pytest.raises(Exception) as exc_info:
            llm.generate("system", "user")

        assert "Persistent error" in str(exc_info.value)


class TestLLMProviderCalls:
    """Tests for provider-specific call methods."""

    @patch('blackreach.llm.LLM._init_client')
    def test_ollama_call_structure(self, mock_init):
        """_call_ollama calls with correct structure."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(model="test-model", temperature=0.5, max_tokens=500)

        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "response"}}
        llm._client = mock_client

        result = llm._call_ollama("system prompt", "user message")

        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args

        assert call_args[1]["model"] == "test-model"
        assert "system" in str(call_args[1]["messages"][0]["role"])
        assert "user" in str(call_args[1]["messages"][1]["role"])
        assert call_args[1]["options"]["temperature"] == 0.5
        assert call_args[1]["options"]["num_predict"] == 500

    @patch('blackreach.llm.LLM._init_client')
    def test_openai_call_structure(self, mock_init):
        """_call_openai calls with correct structure."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(model="gpt-4", temperature=0.7, max_tokens=1024)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="response"))]
        mock_client.chat.completions.create.return_value = mock_response
        llm._client = mock_client

        result = llm._call_openai("system prompt", "user message")

        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args

        assert call_args[1]["model"] == "gpt-4"
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["max_tokens"] == 1024

    @patch('blackreach.llm.LLM._init_client')
    def test_anthropic_call_structure(self, mock_init):
        """_call_anthropic calls with correct structure."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(model="claude-3", max_tokens=2048)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_response
        llm._client = mock_client

        result = llm._call_anthropic("system prompt", "user message")

        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args

        assert call_args[1]["model"] == "claude-3"
        assert call_args[1]["system"] == "system prompt"
        assert call_args[1]["max_tokens"] == 2048
