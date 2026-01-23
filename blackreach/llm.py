"""
Blackreach LLM Integration

Connects to various LLM providers for the agent brain.
Supports: Ollama (local), OpenAI, Anthropic, Google, Groq
"""

import json
import re
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM Configuration."""
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    max_retries: int = 3
    retry_delay: float = 1.0


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
        self._init_client()

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
            raise ValueError(f"Unsupported provider: {provider}")

    def _init_ollama(self):
        """Initialize Ollama client (local models)."""
        try:
            import ollama
            self._client = ollama
            self._provider_type = "ollama"
        except ImportError:
            raise ImportError("ollama package required. Install with: pip install ollama")

    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base
            )
            self._provider_type = "openai"
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

    def _init_anthropic(self):
        """Initialize Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
            self._provider_type = "anthropic"
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def _init_google(self):
        """Initialize Google Gemini client."""
        try:
            from google import genai
            self._client = genai.Client(api_key=self.config.api_key)
            self._provider_type = "google"
        except ImportError:
            raise ImportError("google-genai package required. Install with: pip install google-genai")

    def _init_xai(self):
        """Initialize xAI client (uses OpenAI-compatible API)."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url="https://api.x.ai/v1"
            )
            self._provider_type = "xai"
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Generate a response from the LLM."""
        for attempt in range(self.config.max_retries):
            try:
                if self._provider_type == "ollama":
                    return self._call_ollama(system_prompt, user_message)
                elif self._provider_type == "openai":
                    return self._call_openai(system_prompt, user_message)
                elif self._provider_type == "anthropic":
                    return self._call_anthropic(system_prompt, user_message)
                elif self._provider_type == "google":
                    return self._call_google(system_prompt, user_message)
                elif self._provider_type == "xai":
                    return self._call_openai(system_prompt, user_message)  # xAI uses OpenAI-compatible API
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise
        return ""

    def _call_ollama(self, system_prompt: str, user_message: str) -> str:
        """Call Ollama API."""
        response = self._client.chat(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
        )
        return response["message"]["content"]

    def _call_openai(self, system_prompt: str, user_message: str) -> str:
        """Call OpenAI API."""
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, system_prompt: str, user_message: str) -> str:
        """Call Anthropic API."""
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

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
        return response.text

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

        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', cleaned)

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
