"""
Blackreach LLM Integration

Connects to various LLM providers for the agent brain.
Supports: Ollama (local), OpenAI, Anthropic, Google, Groq
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from blackreach.exceptions import ProviderError, ProviderNotInstalledError
from blackreach.provider_support import (
    classify_error,
    is_reasoning_model,
    provider_error,
    settings_errors,
)

# P0-PERF: Pre-compiled regex for JSON extraction (used on every LLM response)
_RE_JSON_OBJECT = re.compile(r'\{[\s\S]*\}')


@dataclass
class LLMConfig:
    """LLM Configuration."""
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096  # Shared reasoning + visible output budget for Responses
    max_retries: int = 3  # Historical name: total attempts, including the first
    retry_delay: float = 1.0
    timeout_seconds: float = 60.0  # Per-attempt transport timeout
    reasoning_effort: str = "low"
    api_mode: str = "auto"  # OpenAI only: auto, chat, or responses
    use_gpu: bool = True  # Force GPU usage for local models
    num_gpu_layers: int = 999  # Number of layers to offload to GPU (999 = all)
    context_size: str = "large"  # DOM walker element cap: "small" (100), "medium" (150), "large" (200)

    def __post_init__(self):
        errors = settings_errors(self)
        if errors:
            raise provider_error(self.provider, "configuration", "; ".join(errors))


@dataclass
class LLMResponse:
    """Parsed response from the LLM."""
    thought: str
    action: Optional[str]
    args: Dict[str, Any]
    done: bool
    reason: Optional[str] = None
    raw_response: str = ""

    @property
    def is_valid(self) -> bool:
        return self.done or (self.action is not None)


class LLM:
    """
    LLM integration for Blackreach.

    Supports: Ollama (default), OpenAI, Anthropic, Google
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._provider_type = None
        try:
            self._init_client()
        except Exception as exc:
            raise classify_error(self.config.provider, exc) from None

    def _init_client(self):
        """Initialize the appropriate LLM client."""
        provider = self.config.provider.lower()

        if provider == "ollama":
            self._init_ollama()
        elif provider == "openai":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        elif provider == "google":
            self._init_google()
        elif provider == "xai":
            self._init_xai()
        else:
            raise ProviderError(provider, "Unsupported provider")

    def _init_ollama(self):
        """Initialize Ollama client (local models)."""
        try:
            import ollama
            self._client = ollama.Client(host=self.config.api_base, timeout=self.config.timeout_seconds)
            self._provider_type = "ollama"
        except ImportError:
            raise ProviderNotInstalledError("ollama", "ollama")

    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout_seconds,
                max_retries=0,  # Blackreach owns the only retry loop
            )
            self._provider_type = "openai"
        except ImportError:
            raise ProviderNotInstalledError("openai", "openai")

    def _init_anthropic(self):
        """Initialize Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.config.api_key, base_url=self.config.api_base,
                timeout=self.config.timeout_seconds, max_retries=0,
            )
            self._provider_type = "anthropic"
        except ImportError:
            raise ProviderNotInstalledError("anthropic", "anthropic")

    def _init_google(self):
        """Initialize Google Gemini client."""
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(
                api_key=self.config.api_key,
                http_options=types.HttpOptions(
                    base_url=self.config.api_base,
                    timeout=int(self.config.timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            self._provider_type = "google"
        except ImportError:
            raise ProviderNotInstalledError("google", "google-genai")

    def _init_xai(self):
        """Initialize xAI client (uses OpenAI-compatible API)."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base or "https://api.x.ai/v1",
                timeout=self.config.timeout_seconds,
                max_retries=0,
            )
            self._provider_type = "xai"
        except ImportError:
            raise ProviderNotInstalledError("xai", "openai")

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System-level instructions for the LLM
            user_message: The user's message/prompt to respond to

        Returns:
            The generated text response from the LLM

        Raises:
            ProviderError: Safe actionable failure after bounded transient retries.
        """
        for attempt in range(self.config.max_retries):
            try:
                call = {
                    "ollama": self._call_ollama, "openai": self._call_openai,
                    "anthropic": self._call_anthropic, "google": self._call_google,
                    "xai": self._call_openai,
                }.get(self._provider_type)
                if call is None:
                    raise provider_error(self.config.provider, "configuration", "Unsupported provider")
                return self._require_text(call(system_prompt, user_message))
            except Exception as exc:
                error = classify_error(self.config.provider, exc)
                error.details["attempts"] = attempt + 1
                if getattr(error, "retryable", False) and attempt < self.config.max_retries - 1:
                    time.sleep(min(self.config.retry_delay * (2 ** attempt), 60.0))
                    continue
                error.recoverable = False
                raise error from None

    def _require_text(self, text: Any) -> str:
        if not isinstance(text, str) or not text.strip():
            raise provider_error(self.config.provider, "empty_output", "Model returned no usable text. Check model capabilities and output budget.")
        return text

    def _call_ollama(self, system_prompt: str, user_message: str) -> str:
        """Call Ollama API with GPU acceleration."""
        options = {
            "temperature": self.config.temperature,
            "num_predict": self.config.max_tokens,
        }

        # Enable GPU acceleration if configured
        if self.config.use_gpu:
            options["num_gpu"] = self.config.num_gpu_layers

        response = self._client.chat(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            options=options
        )
        if response.get("done_reason") == "length":
            raise self._output_limit()
        return self._require_text(response["message"]["content"])

    def complete(self, prompt: str) -> str:
        """Simple completion interface (convenience method).

        Args:
            prompt: The prompt to complete

        Returns:
            Generated text response
        """
        return self.generate("You are a helpful assistant.", prompt)

    def _call_openai(self, system_prompt: str, user_message: str) -> str:
        """Route OpenAI reasoning models to Responses; keep compatible APIs on Chat."""
        native_openai = self.config.provider.lower() == "openai"
        reasoning = native_openai and is_reasoning_model(self.config.model)
        modern_openai = native_openai and self.config.model.lower().startswith(("gpt-5", "gpt-6"))
        responses = native_openai and (
            self.config.api_mode == "responses" or (self.config.api_mode == "auto" and (reasoning or modern_openai))
        )
        if responses:
            resource = getattr(self._client, "responses", None)
            if resource is None:
                raise provider_error("openai", "configuration", "Responses requires openai>=1.66.0. Upgrade the OpenAI extra.")
            kwargs = dict(
                model=self.config.model, instructions=system_prompt, input=user_message,
                max_output_tokens=self.config.max_tokens, store=False,
            )
            if reasoning:
                kwargs["reasoning"] = {"effort": self.config.reasoning_effort}
            response = resource.create(**kwargs)
            status = getattr(response, "status", None)
            if status == "incomplete":
                reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
                if reason == "max_output_tokens":
                    raise self._output_limit()
                if reason == "content_filter":
                    raise provider_error("openai", "content_filter", "Provider filtered the response. Revise the task.")
                raise provider_error("openai", "invalid_response", "Provider returned an incomplete response. No action was accepted.")
            if status == "failed":
                code = getattr(getattr(response, "error", None), "code", None)
                raise provider_error("openai", "unavailable" if code == "server_error" else "provider_failure", "Provider failed to generate a response.", retryable=code == "server_error")
            if status != "completed":
                raise provider_error("openai", "invalid_response", "Provider did not return a completed response. No action was accepted.")
            for item in getattr(response, "output", None) or []:
                for part in getattr(item, "content", None) or []:
                    if getattr(part, "type", None) == "refusal":
                        raise provider_error("openai", "refusal", "Model declined the request. Revise the task.")
            return self._require_text(getattr(response, "output_text", None))

        kwargs = dict(
            model=self.config.model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        )
        if reasoning or modern_openai:
            kwargs["max_completion_tokens"] = self.config.max_tokens
            if reasoning:
                kwargs["reasoning_effort"] = self.config.reasoning_effort
        else:
            kwargs.update(temperature=self.config.temperature, max_tokens=self.config.max_tokens)
        response = self._client.chat.completions.create(**kwargs)
        choices = response.choices
        if not choices:
            raise provider_error(self.config.provider, "empty_output", "Provider returned no completion choices.")
        choice = choices[0]
        if choice.finish_reason == "length":
            raise self._output_limit()
        if choice.finish_reason == "content_filter":
            raise provider_error(self.config.provider, "content_filter", "Provider filtered the response. Revise the task.")
        if isinstance(choice.finish_reason, str) and choice.finish_reason != "stop":
            raise provider_error(self.config.provider, "invalid_response", "Provider did not finish a text response. No action was accepted.")
        if isinstance(getattr(choice.message, "refusal", None), str) and choice.message.refusal:
            raise provider_error(self.config.provider, "refusal", "Model declined the request. Revise the task.")
        return self._require_text(choice.message.content)

    def _output_limit(self) -> ProviderError:
        return provider_error(
            self.config.provider, "output_limit",
            f"Response reached the output limit (max_tokens={self.config.max_tokens}). "
            "Increase max_tokens or reduce reasoning_effort; reasoning and visible output share this budget. No partial action was accepted.",
        )

    def _call_anthropic(self, system_prompt: str, user_message: str) -> str:
        """Call Anthropic API."""
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise self._output_limit()
        if getattr(response, "stop_reason", None) == "refusal":
            raise provider_error("anthropic", "refusal", "Model declined the request. Revise the task.")
        return self._require_text("".join(
            part.text for part in response.content if isinstance(getattr(part, "text", None), str)
        ))

    def _call_google(self, system_prompt: str, user_message: str) -> str:
        """Call Google Gemini API."""
        from google.genai import types

        full_prompt = f"{system_prompt}\n\n{user_message}"

        response = self._client.models.generate_content(
            model=self.config.model,
            contents=[types.Content(
                role="user",
                parts=[types.Part(text=full_prompt)]
            )],
            config=types.GenerateContentConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            )
        )
        for candidate in getattr(response, "candidates", None) or []:
            reason = str(getattr(candidate, "finish_reason", ""))
            if reason.endswith("MAX_TOKENS"):
                raise self._output_limit()
            if reason.endswith(("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION")):
                raise provider_error("google", "content_filter", "Provider filtered the response. Revise the task.")
        return self._require_text(response.text)

    def parse_action(self, response_text: str) -> LLMResponse:
        """Parse LLM response to extract action."""
        cleaned = response_text.strip()

        # Strip markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Find JSON in response (using precompiled regex)
        json_match = _RE_JSON_OBJECT.search(cleaned)

        if not json_match:
            return LLMResponse(
                thought="Failed to parse response - no JSON found",
                action=None,
                args={},
                done=False,
                raw_response=response_text
            )

        try:
            data = json.loads(json_match.group())

            action = data.get("action")
            done = data.get("done", False)
            reason = data.get("reason")

            # Handle action: "done" format
            if action == "done":
                done = True
                reason = reason or data.get("args", {}).get("reason", "Goal complete")

            return LLMResponse(
                thought=data.get("thought", ""),
                action=action,
                args=data.get("args", {}),
                done=done,
                reason=reason,
                raw_response=response_text
            )
        except json.JSONDecodeError as e:
            return LLMResponse(
                thought=f"JSON parse error: {str(e)}",
                action=None,
                args={},
                done=False,
                raw_response=response_text
            )
