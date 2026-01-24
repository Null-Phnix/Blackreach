"""
Blackreach Configuration Manager

Handles:
- API keys for different providers
- Default model settings
- User preferences
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

from blackreach.exceptions import InvalidConfigError


CONFIG_DIR = Path.home() / ".blackreach"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
FIRST_RUN_MARKER = CONFIG_DIR / ".initialized"


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    api_key: str = ""
    default_model: str = ""
    base_url: str = ""  # For custom endpoints


@dataclass
class Config:
    """Main configuration."""
    # Default provider
    default_provider: str = "ollama"

    # Provider configs
    ollama: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="qwen2.5:7b"
    ))
    openai: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="gpt-4o-mini"
    ))
    anthropic: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="claude-3-5-sonnet-20241022"
    ))
    google: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="gemini-2.5-flash"
    ))
    xai: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="grok-4-fast-non-reasoning"
    ))

    # Agent settings
    headless: bool = False
    max_steps: int = 30
    download_dir: str = "./downloads"
    browser_type: str = "chromium"  # chromium, firefox, or webkit

    # UI settings
    verbose: bool = True
    show_thinking: bool = True


# Available models per provider
AVAILABLE_MODELS = {
    "ollama": [
        "qwen2.5:7b",
        "qwen2.5:14b",
        "llama3.2:3b",
        "llama3.1:8b",
        "mistral:7b",
        "phi3:mini",
        "gemma2:9b",
        "codellama:7b",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ],
    "xai": [
        "grok-4-1-fast-reasoning",
        "grok-4-1-fast-non-reasoning",
        "grok-4-fast-reasoning",
        "grok-4-fast-non-reasoning",
        "grok-code-fast-1",
        "grok-3-mini",
        "grok-3",
    ],
}


class ConfigManager:
    """Manages Blackreach configuration."""

    def __init__(self):
        self._config: Optional[Config] = None
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Load configuration from file or create default."""
        if self._config:
            return self._config

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = yaml.safe_load(f) or {}
                self._config = self._dict_to_config(data)
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
                self._config = Config()
        else:
            self._config = Config()
            self.save()  # Create default config file

        # Also check environment variables for API keys
        self._load_env_keys()

        return self._config

    def _load_env_keys(self):
        """Load API keys from environment variables."""
        if not self._config:
            return

        env_mappings = {
            "OPENAI_API_KEY": ("openai", "api_key"),
            "ANTHROPIC_API_KEY": ("anthropic", "api_key"),
            "GOOGLE_API_KEY": ("google", "api_key"),
            "XAI_API_KEY": ("xai", "api_key"),
        }

        for env_var, (provider, attr) in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                provider_config = getattr(self._config, provider)
                setattr(provider_config, attr, value)

    def save(self):
        """Save configuration to file."""
        if not self._config:
            self._config = Config()

        data = self._config_to_dict(self._config)

        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def _config_to_dict(self, config: Config) -> Dict[str, Any]:
        """Convert Config to dictionary for YAML."""
        return {
            "default_provider": config.default_provider,
            "providers": {
                "ollama": asdict(config.ollama),
                "openai": asdict(config.openai),
                "anthropic": asdict(config.anthropic),
                "google": asdict(config.google),
                "xai": asdict(config.xai),
            },
            "agent": {
                "headless": config.headless,
                "max_steps": config.max_steps,
                "download_dir": config.download_dir,
                "browser_type": config.browser_type,
            },
            "ui": {
                "verbose": config.verbose,
                "show_thinking": config.show_thinking,
            }
        }

    def _dict_to_config(self, data: Dict[str, Any]) -> Config:
        """Convert dictionary to Config."""
        config = Config()

        config.default_provider = data.get("default_provider", "ollama")

        providers = data.get("providers", {})
        for name in ["ollama", "openai", "anthropic", "google", "xai"]:
            if name in providers:
                p = providers[name]
                setattr(config, name, ProviderConfig(
                    api_key=p.get("api_key", ""),
                    default_model=p.get("default_model", ""),
                    base_url=p.get("base_url", "")
                ))

        agent = data.get("agent", {})
        config.headless = agent.get("headless", False)
        config.max_steps = agent.get("max_steps", 30)
        config.download_dir = agent.get("download_dir", "./downloads")
        config.browser_type = agent.get("browser_type", "chromium")

        ui = data.get("ui", {})
        config.verbose = ui.get("verbose", True)
        config.show_thinking = ui.get("show_thinking", True)

        return config

    def set_api_key(self, provider: str, key: str):
        """Set API key for a provider."""
        config = self.load()
        if hasattr(config, provider):
            getattr(config, provider).api_key = key
            self.save()
        else:
            raise InvalidConfigError("provider", provider, "one of: anthropic, openai, google, ollama, xai")

    def set_default_provider(self, provider: str):
        """Set the default provider."""
        config = self.load()
        if provider in AVAILABLE_MODELS:
            config.default_provider = provider
            self.save()
        else:
            raise InvalidConfigError("provider", provider, f"one of: {', '.join(AVAILABLE_MODELS.keys())}")

    def set_default_model(self, provider: str, model: str):
        """Set default model for a provider."""
        config = self.load()
        if hasattr(config, provider):
            getattr(config, provider).default_model = model
            self.save()
        else:
            raise InvalidConfigError("provider", provider, "one of: anthropic, openai, google, ollama, xai")

    def get_current_provider(self) -> str:
        """Get current default provider."""
        return self.load().default_provider

    def get_current_model(self) -> str:
        """Get current default model."""
        config = self.load()
        provider = config.default_provider
        return getattr(config, provider).default_model

    def get_api_key(self, provider: str) -> str:
        """Get API key for provider."""
        config = self.load()
        if hasattr(config, provider):
            return getattr(config, provider).api_key
        return ""

    def has_api_key(self, provider: str) -> bool:
        """Check if provider has API key configured."""
        return bool(self.get_api_key(provider))


# Global config manager instance
config_manager = ConfigManager()
