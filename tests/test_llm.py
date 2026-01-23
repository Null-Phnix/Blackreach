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
    def test_parse_strips_generic_markdown(self, mock_init):
        """parse_action strips generic markdown code blocks (no json)."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig()
        llm._client = None

        result = llm.parse_action('```\n{"action": "navigate"}\n```')

        assert result.action == "navigate"

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

    @patch('blackreach.llm.LLM._init_client')
    def test_google_call_structure(self, mock_init):
        """_call_google calls with correct structure."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(model="gemini-pro", temperature=0.5, max_tokens=1024)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "response"
        mock_client.models.generate_content.return_value = mock_response
        llm._client = mock_client

        # Mock the google.genai.types import
        with patch.dict('sys.modules', {'google.genai': MagicMock(), 'google.genai.types': MagicMock()}):
            from unittest.mock import MagicMock as MM
            mock_types = MM()
            mock_types.Content.return_value = "content"
            mock_types.Part.return_value = "part"
            mock_types.GenerateContentConfig.return_value = "config"

            with patch('blackreach.llm.LLM._call_google') as mock_call:
                mock_call.return_value = "response"
                result = mock_call("system prompt", "user message")

            assert result == "response"


class TestLLMProviderInit:
    """Tests for provider initialization."""

    def test_ollama_import_error(self):
        """Raises ProviderNotInstalledError when ollama not installed."""
        with patch.dict('sys.modules', {'ollama': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig(provider="ollama")
                llm._client = None
                llm._provider_type = None

                with pytest.raises(ProviderNotInstalledError):
                    llm._init_ollama()

    def test_openai_import_error(self):
        """Raises ProviderNotInstalledError when openai not installed."""
        with patch.dict('sys.modules', {'openai': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig(provider="openai", api_key="test")
                llm._client = None
                llm._provider_type = None

                with pytest.raises(ProviderNotInstalledError):
                    llm._init_openai()

    def test_anthropic_import_error(self):
        """Raises ProviderNotInstalledError when anthropic not installed."""
        with patch.dict('sys.modules', {'anthropic': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig(provider="anthropic", api_key="test")
                llm._client = None
                llm._provider_type = None

                with pytest.raises(ProviderNotInstalledError):
                    llm._init_anthropic()

    def test_google_import_error(self):
        """Raises ProviderNotInstalledError when google-genai not installed."""
        with patch.dict('sys.modules', {'google': None, 'google.genai': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig(provider="google", api_key="test")
                llm._client = None
                llm._provider_type = None

                with pytest.raises(ProviderNotInstalledError):
                    llm._init_google()

    def test_xai_import_error(self):
        """Raises ProviderNotInstalledError when openai not installed for xAI."""
        with patch.dict('sys.modules', {'openai': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig(provider="xai", api_key="test")
                llm._client = None
                llm._provider_type = None

                with pytest.raises(ProviderNotInstalledError):
                    llm._init_xai()


class TestLLMGenerateProviderDispatch:
    """Tests for generate method provider dispatch."""

    @patch('blackreach.llm.LLM._init_client')
    def test_generate_dispatches_to_openai(self, mock_init):
        """generate dispatches to OpenAI provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=1)
        llm._client = MagicMock()
        llm._provider_type = "openai"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="openai response"))]
        llm._client.chat.completions.create.return_value = mock_response

        result = llm.generate("system", "user")

        assert result == "openai response"

    @patch('blackreach.llm.LLM._init_client')
    def test_generate_dispatches_to_anthropic(self, mock_init):
        """generate dispatches to Anthropic provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=1)
        llm._client = MagicMock()
        llm._provider_type = "anthropic"

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="anthropic response")]
        llm._client.messages.create.return_value = mock_response

        result = llm.generate("system", "user")

        assert result == "anthropic response"

    @patch('blackreach.llm.LLM._init_client')
    def test_generate_dispatches_to_xai(self, mock_init):
        """generate dispatches to xAI provider (uses OpenAI client)."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=1)
        llm._client = MagicMock()
        llm._provider_type = "xai"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="xai response"))]
        llm._client.chat.completions.create.return_value = mock_response

        result = llm.generate("system", "user")

        assert result == "xai response"

    @patch('blackreach.llm.LLM._init_client')
    @patch('blackreach.llm.LLM._call_google')
    def test_generate_dispatches_to_google(self, mock_call_google, mock_init):
        """generate dispatches to Google provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(max_retries=1)
        llm._client = MagicMock()
        llm._provider_type = "google"

        mock_call_google.return_value = "google response"

        result = llm.generate("system", "user")

        assert result == "google response"
        mock_call_google.assert_called_once_with("system", "user")


class TestLLMProviderInitSuccess:
    """Tests for successful provider initialization."""

    def test_openai_init_success(self):
        """_init_openai initializes client when openai is installed."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="openai", api_key="test-key", api_base=None)
        llm._client = None
        llm._provider_type = None

        mock_openai_class = MagicMock()
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai_class)}):
            # Re-import to get the patched module
            import importlib
            import blackreach.llm as llm_module

            # Call the method directly with mocked import
            with patch.object(llm_module, 'LLM') as mock_llm:
                # Test that OpenAI provider path in _init_client is covered
                llm2 = LLM.__new__(LLM)
                llm2.config = LLMConfig(provider="openai", api_key="key")
                llm2._client = None
                llm2._provider_type = None

                # Mock the import within the method
                mock_openai_module = MagicMock()
                mock_client = MagicMock()
                mock_openai_module.OpenAI.return_value = mock_client

                with patch.dict('sys.modules', {'openai': mock_openai_module}):
                    llm2._init_openai()

                assert llm2._client == mock_client
                assert llm2._provider_type == "openai"

    def test_anthropic_init_success(self):
        """_init_anthropic initializes client when anthropic is installed."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="anthropic", api_key="test-key")
        llm._client = None
        llm._provider_type = None

        mock_anthropic_module = MagicMock()
        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch.dict('sys.modules', {'anthropic': mock_anthropic_module}):
            llm._init_anthropic()

        assert llm._client == mock_client
        assert llm._provider_type == "anthropic"

    def test_google_init_success(self):
        """_init_google initializes client when google-genai is installed."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="google", api_key="test-key")
        llm._client = None
        llm._provider_type = None

        mock_google_module = MagicMock()
        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_google_module.genai = mock_genai

        with patch.dict('sys.modules', {'google': mock_google_module, 'google.genai': mock_genai}):
            llm._init_google()

        assert llm._client == mock_client
        assert llm._provider_type == "google"

    def test_xai_init_success(self):
        """_init_xai initializes client with xAI base URL."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="xai", api_key="test-key")
        llm._client = None
        llm._provider_type = None

        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict('sys.modules', {'openai': mock_openai_module}):
            llm._init_xai()

        assert llm._client == mock_client
        assert llm._provider_type == "xai"
        # Verify xAI base URL was used
        mock_openai_module.OpenAI.assert_called_once()
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] == "https://api.x.ai/v1"


class TestCallGoogle:
    """Tests for _call_google method."""

    @patch('blackreach.llm.LLM._init_client')
    def test_call_google_uses_types(self, mock_init):
        """_call_google uses google.genai.types for content creation."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(model="gemini-pro", temperature=0.5, max_tokens=1024)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "google response text"
        mock_client.models.generate_content.return_value = mock_response
        llm._client = mock_client

        # Create mock types module
        mock_types = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_config = MagicMock()
        mock_types.Content.return_value = mock_content
        mock_types.Part.return_value = mock_part
        mock_types.GenerateContentConfig.return_value = mock_config

        with patch.dict('sys.modules', {'google.genai.types': mock_types, 'google.genai': MagicMock(types=mock_types)}):
            result = llm._call_google("system prompt", "user message")

        assert result == "google response text"
        mock_client.models.generate_content.assert_called_once()


class TestLLMInitClientDispatch:
    """Tests for _init_client provider dispatch."""

    def test_init_client_dispatches_to_openai(self):
        """_init_client calls _init_openai for openai provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="openai", api_key="key")
        llm._client = None
        llm._provider_type = None

        with patch.object(llm, '_init_openai') as mock_init:
            llm._init_client()
            mock_init.assert_called_once()

    def test_init_client_dispatches_to_anthropic(self):
        """_init_client calls _init_anthropic for anthropic provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="anthropic", api_key="key")
        llm._client = None
        llm._provider_type = None

        with patch.object(llm, '_init_anthropic') as mock_init:
            llm._init_client()
            mock_init.assert_called_once()

    def test_init_client_dispatches_to_google(self):
        """_init_client calls _init_google for google provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="google", api_key="key")
        llm._client = None
        llm._provider_type = None

        with patch.object(llm, '_init_google') as mock_init:
            llm._init_client()
            mock_init.assert_called_once()

    def test_init_client_dispatches_to_xai(self):
        """_init_client calls _init_xai for xai provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="xai", api_key="key")
        llm._client = None
        llm._provider_type = None

        with patch.object(llm, '_init_xai') as mock_init:
            llm._init_client()
            mock_init.assert_called_once()

    def test_init_client_dispatches_to_ollama(self):
        """_init_client calls _init_ollama for ollama provider."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="ollama")
        llm._client = None
        llm._provider_type = None

        with patch.object(llm, '_init_ollama') as mock_init:
            llm._init_client()
            mock_init.assert_called_once()


class TestLLMConstructor:
    """Tests for LLM __init__ constructor."""

    def test_init_with_default_config(self):
        """LLM creates default config when none provided."""
        mock_ollama = MagicMock()

        with patch.dict('sys.modules', {'ollama': mock_ollama}):
            llm = LLM()

        assert llm.config is not None
        assert llm.config.provider == "ollama"

    def test_init_with_custom_config(self):
        """LLM uses provided config."""
        config = LLMConfig(provider="ollama", model="custom-model")
        mock_ollama = MagicMock()

        with patch.dict('sys.modules', {'ollama': mock_ollama}):
            llm = LLM(config)

        assert llm.config.model == "custom-model"

    def test_init_calls_init_client(self):
        """LLM __init__ calls _init_client."""
        mock_ollama = MagicMock()

        with patch.dict('sys.modules', {'ollama': mock_ollama}):
            with patch.object(LLM, '_init_client') as mock_init:
                # Need to bypass the real init that calls _init_client
                llm = LLM.__new__(LLM)
                llm.config = LLMConfig()
                llm._client = None
                llm._provider_type = None
                llm._init_client()

                mock_init.assert_called_once()


class TestOllamaInitSuccess:
    """Tests for successful Ollama initialization."""

    def test_ollama_init_sets_client_and_type(self):
        """_init_ollama sets client and provider type."""
        llm = LLM.__new__(LLM)
        llm.config = LLMConfig(provider="ollama")
        llm._client = None
        llm._provider_type = None

        mock_ollama = MagicMock()

        with patch.dict('sys.modules', {'ollama': mock_ollama}):
            llm._init_ollama()

        assert llm._client == mock_ollama
        assert llm._provider_type == "ollama"
