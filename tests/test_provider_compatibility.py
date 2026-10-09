"""Provider contract regressions. All transports are mocked; no live inference."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from blackreach.config import AVAILABLE_MODELS
from blackreach.exceptions import ProviderError
from blackreach.llm import LLM, LLMConfig


@pytest.fixture(autouse=True)
def mock_optional_sdks():
    """Unit contracts must also run with the base package's optional SDKs absent."""
    google_types = SimpleNamespace(
        HttpOptions=SimpleNamespace, HttpRetryOptions=SimpleNamespace,
        Content=SimpleNamespace, Part=SimpleNamespace, GenerateContentConfig=SimpleNamespace,
    )
    genai = SimpleNamespace(Client=MagicMock(), types=google_types)
    with patch.dict("sys.modules", {
        "openai": SimpleNamespace(OpenAI=MagicMock()),
        "anthropic": SimpleNamespace(Anthropic=MagicMock()),
        "google": SimpleNamespace(genai=genai),
        "google.genai": genai, "google.genai.types": google_types,
    }):
        yield


def make_llm(provider="openai", model="gpt-6-luna", **settings):
    with patch.object(LLM, "_init_client"):
        llm = LLM(LLMConfig(provider=provider, model=model, **settings))
    llm._provider_type = provider
    llm._client = MagicMock()
    return llm


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol", "gpt-5.6-luna", "o3", "o4-mini"])
def test_reasoning_models_use_responses(model):
    llm = make_llm(model=model, max_tokens=4096)
    llm._client.responses.create.return_value = SimpleNamespace(status="completed", output_text='{"action":"done"}')
    assert llm.generate("system", "user") == '{"action":"done"}'
    assert llm._client.responses.create.call_args.kwargs == dict(
        model=model, instructions="system", input="user", max_output_tokens=4096,
        reasoning={"effort": "low"}, store=False,
    )
    llm._client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize("text", ["", '{"action":"done"}'])
def test_incomplete_responses_never_become_actions_or_retry(text):
    llm = make_llm()
    llm._client.responses.create.return_value = SimpleNamespace(status="incomplete", output_text=text, incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    with pytest.raises(ProviderError, match="max_tokens") as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "output_limit"
    assert llm._client.responses.create.call_count == 1


def test_current_models_are_selectable():
    assert {"gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol"} <= set(AVAILABLE_MODELS["openai"])


@pytest.mark.parametrize("provider,model", [("openai", "gpt-4o-mini"), ("xai", "gpt-6-custom")])
def test_chat_compatibility_preserved(provider, model):
    llm = make_llm(provider=provider, model=model, max_tokens=1024)
    llm._client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok", refusal=None))])
    assert llm.generate("system", "user") == "ok"
    kwargs = llm._client.chat.completions.create.call_args.kwargs
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 1024
    assert "reasoning_effort" not in kwargs
    llm._client.responses.create.assert_not_called()


def test_explicit_chat_reasoning_uses_current_token_parameter():
    llm = make_llm(api_mode="chat")
    llm._client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok", refusal=None))])
    assert llm.generate("system", "user") == "ok"
    kwargs = llm._client.chat.completions.create.call_args.kwargs
    assert kwargs["max_completion_tokens"] == 4096
    assert kwargs["reasoning_effort"] == "low"
    assert "temperature" not in kwargs and "max_tokens" not in kwargs


def test_explicit_responses_for_legacy_model_omits_reasoning():
    llm = make_llm(model="gpt-4.1", api_mode="responses")
    llm._client.responses.create.return_value = SimpleNamespace(status="completed", output_text="ok")
    assert llm.generate("system", "user") == "ok"
    assert "reasoning" not in llm._client.responses.create.call_args.kwargs


@pytest.mark.parametrize("text", [None, "", " \n"])
def test_empty_completed_response_fails_without_retries(text):
    llm = make_llm()
    llm._client.responses.create.return_value = SimpleNamespace(status="completed", output_text=text)
    with pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "empty_output"
    assert caught.value.details["attempts"] == 1
    assert llm._client.responses.create.call_count == 1


@pytest.mark.parametrize("status", ["failed", "in_progress", "queued", "cancelled", None])
def test_noncompleted_status_is_not_text(status):
    llm = make_llm()
    llm._client.responses.create.return_value = SimpleNamespace(status=status, output_text='{"action":"done"}')
    with pytest.raises(ProviderError):
        llm.generate("system", "user")


def test_refusal_is_not_action_text():
    llm = make_llm()
    llm._client.responses.create.return_value = SimpleNamespace(status="completed", output_text='{"action":"done"}', output=[SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="private content")])])
    with pytest.raises(ProviderError, match="declined") as caught:
        llm.generate("system", "user")
    assert "private content" not in str(caught.value)


@pytest.mark.parametrize("finish,code", [("length", "output_limit"), ("content_filter", "content_filter")])
def test_chat_truncation_is_not_action_text(finish, code):
    llm = make_llm(model="gpt-4o")
    llm._client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content='{"action":"done"}'))])
    with pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == code
    assert llm._client.chat.completions.create.call_count == 1


class SDKFailureError(Exception):
    def __init__(self, status=None, code=None):
        super().__init__("sensitive request body sk-private api_key=secret")
        self.status_code = status
        self.body = {"error": {"code": code, "message": "sensitive provider body"}}


@pytest.mark.parametrize("status,provider_code,code", [
    (400, None, "invalid_request"), (401, None, "authentication"),
    (403, None, "permission"), (404, None, "model_not_found"),
    (400, "model_not_found", "model_not_found"),
    (429, "insufficient_quota", "quota"), (422, None, "invalid_request"),
])
def test_permanent_errors_stop_and_redact(status, provider_code, code):
    llm = make_llm()
    llm._client.responses.create.side_effect = SDKFailureError(status, provider_code)
    with patch("blackreach.llm.time.sleep") as sleep, pytest.raises(ProviderError) as caught:
        llm.generate("sensitive system prompt", "sensitive input")
    error = caught.value
    assert error.details["code"] == code
    assert error.details["status_code"] == status
    assert error.details["attempts"] == 1
    assert error.recoverable is False
    assert "sensitive" not in str(error) and "secret" not in str(error)
    assert error.__cause__ is None and error.__suppress_context__ is True
    assert llm._client.responses.create.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("error,code", [(SDKFailureError(429), "rate_limit"), (SDKFailureError(500), "unavailable"), (TimeoutError("sensitive"), "timeout"), (ConnectionError("sensitive"), "connection")])
def test_transient_failures_have_one_bounded_retry_loop(error, code):
    llm = make_llm(max_retries=3, retry_delay=0.5)
    llm._client.responses.create.side_effect = error
    with patch("blackreach.llm.time.sleep") as sleep, pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == code
    assert caught.value.details["attempts"] == 3
    assert caught.value.recoverable is False
    assert llm._client.responses.create.call_count == 3
    assert [args.args[0] for args in sleep.call_args_list] == [0.5, 1.0]


def test_transient_then_success_retries_only_failed_attempt():
    llm = make_llm()
    llm._client.responses.create.side_effect = [SDKFailureError(503), SimpleNamespace(status="completed", output_text="ok")]
    with patch("blackreach.llm.time.sleep"):
        assert llm.generate("system", "user") == "ok"
    assert llm._client.responses.create.call_count == 2


def test_unknown_exception_does_not_retry_or_echo():
    llm = make_llm()
    llm._client.responses.create.side_effect = RuntimeError("private request or SDK defect")
    with pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "provider_failure"
    assert "private" not in str(caught.value)
    assert llm._client.responses.create.call_count == 1


@pytest.mark.parametrize("settings", [
    {"max_retries": 0}, {"max_retries": 11}, {"max_tokens": 0}, {"max_tokens": True},
    {"timeout_seconds": 0}, {"timeout_seconds": float("inf")}, {"retry_delay": -1},
    {"api_mode": "invalid"}, {"reasoning_effort": "invalid"},
    {"provider": "xai", "api_mode": "responses"},
])
def test_invalid_request_settings_fail_before_client_init(settings):
    with patch.object(LLM, "_init_client") as init, pytest.raises(ProviderError):
        LLM(LLMConfig(**settings))
    init.assert_not_called()


@pytest.mark.parametrize("provider", ["openai", "xai"])
def test_openai_compatible_client_timeout_and_sdk_retries(provider):
    with patch("openai.OpenAI") as client:
        LLM(LLMConfig(provider=provider, model="example", api_key="dummy", api_base="https://example.test/v1", timeout_seconds=12))
    kwargs = client.call_args.kwargs
    assert kwargs["timeout"] == 12
    assert kwargs["max_retries"] == 0
    assert kwargs["base_url"] == "https://example.test/v1"


def test_anthropic_client_timeout_and_sdk_retries():
    with patch("anthropic.Anthropic") as client:
        LLM(LLMConfig(provider="anthropic", api_key="dummy", timeout_seconds=12))
    assert client.call_args.kwargs["timeout"] == 12
    assert client.call_args.kwargs["max_retries"] == 0


def test_google_client_timeout_and_sdk_retries():
    with patch("google.genai.Client") as client:
        LLM(LLMConfig(provider="google", api_key="dummy", timeout_seconds=12))
    options = client.call_args.kwargs["http_options"]
    assert options.timeout == 12000
    assert options.retry_options.attempts == 1


def test_ollama_client_timeout():
    with patch("ollama.Client") as client:
        LLM(LLMConfig(provider="ollama", api_base="http://example.test", timeout_seconds=12))
    client.assert_called_once_with(host="http://example.test", timeout=12)


@pytest.mark.parametrize("provider", ["ollama", "anthropic", "google"])
def test_other_provider_output_limits_fail_closed(provider):
    llm = make_llm(provider=provider, model="example")
    if provider == "ollama":
        llm._client.chat.return_value = {"message": {"content": '{"action":"done"}'}, "done_reason": "length"}
    elif provider == "anthropic":
        llm._client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(type="text", text='{"action":"done"}')], stop_reason="max_tokens")
    else:
        llm._client.models.generate_content.return_value = SimpleNamespace(text='{"action":"done"}', candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")])
    with pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "output_limit"


def test_anthropic_text_skips_thinking_blocks():
    llm = make_llm(provider="anthropic", model="example")
    llm._client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="private"), SimpleNamespace(type="text", text="ok")], stop_reason="end_turn")
    assert llm.generate("system", "user") == "ok"


@pytest.mark.parametrize("model", ["gpt-5-chat-latest", "gpt-5.1-chat-latest"])
def test_nonreasoning_chat_variant_never_receives_reasoning_parameter(model):
    llm = make_llm(model=model)
    llm._client.responses.create.return_value = SimpleNamespace(status="completed", output_text="ok")
    assert llm.generate("system", "user") == "ok"
    assert "reasoning" not in llm._client.responses.create.call_args.kwargs


@pytest.mark.parametrize("finish_reason", ["tool_calls", "function_call"])
def test_unhandled_tool_completion_never_becomes_action(finish_reason):
    llm = make_llm(model="gpt-4o")
    llm._client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content='{"action":"done"}'))])
    with pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "invalid_response"


def test_missing_responses_sdk_has_actionable_error():
    llm = make_llm()
    llm._client.responses = None
    with pytest.raises(ProviderError, match="openai>=1.66.0") as caught:
        llm.generate("system", "user")
    assert caught.value.details["code"] == "configuration"


def test_client_init_errors_are_safe():
    with patch("openai.OpenAI", side_effect=ValueError("api_key=private")), pytest.raises(ProviderError) as caught:
        LLM(LLMConfig(provider="openai", api_key="dummy"))
    assert "private" not in str(caught.value)


def test_sdk_server_failure_is_bounded():
    llm = make_llm(max_retries=2)
    llm._client.responses.create.return_value = SimpleNamespace(status="failed", output_text=None, error=SimpleNamespace(code="server_error", message="private"))
    with patch("blackreach.llm.time.sleep"), pytest.raises(ProviderError) as caught:
        llm.generate("system", "user")
    assert caught.value.details["attempts"] == 2
    assert caught.value.details["code"] == "unavailable"
    assert "private" not in str(caught.value)
