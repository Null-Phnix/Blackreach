"""
Blackreach Configuration Manager

Handles:
- API keys for different providers
- Default model settings
- User preferences
- Configuration validation
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
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


# =============================================================================
# Configuration Validation
# =============================================================================

@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    def __bool__(self) -> bool:
        """Return True if validation passed."""
        return self.valid


class ConfigValidator:
    """
    Validates Blackreach configuration.

    Checks:
    - Required fields are present
    - Values are within valid ranges
    - API keys have correct format
    - Paths are valid
    - Provider/model combinations are valid
    """

    # API key patterns for basic format validation
    API_KEY_PATTERNS = {
        "openai": re.compile(r"^sk-[a-zA-Z0-9_-]{20,}$"),
        "anthropic": re.compile(r"^sk-ant-[a-zA-Z0-9_-]{20,}$"),
        "google": re.compile(r"^AIza[a-zA-Z0-9_-]{30,}$"),
        "xai": re.compile(r"^xai-[a-zA-Z0-9_-]{20,}$"),
    }

    # Valid ranges for numeric settings
    VALID_RANGES = {
        "max_steps": (1, 1000),
        "timeout": (1, 600),
    }

    def __init__(self):
        pass

    def validate(self, config: Config) -> ValidationResult:
        """
        Perform full configuration validation.

        Args:
            config: Config object to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)

        # Validate provider
        self._validate_provider(config, result)

        # Validate agent settings
        self._validate_agent_settings(config, result)

        # Validate paths
        self._validate_paths(config, result)

        # Validate API keys for active provider
        self._validate_api_keys(config, result)

        # Validate model selection
        self._validate_model(config, result)

        return result

    def _validate_provider(self, config: Config, result: ValidationResult) -> None:
        """Validate provider configuration."""
        if not config.default_provider:
            result.add_error("default_provider is required")
            return

        if config.default_provider not in AVAILABLE_MODELS:
            result.add_error(
                f"Invalid provider '{config.default_provider}'. "
                f"Valid options: {', '.join(AVAILABLE_MODELS.keys())}"
            )

    def _validate_agent_settings(self, config: Config, result: ValidationResult) -> None:
        """Validate agent-related settings."""
        # max_steps
        min_steps, max_steps = self.VALID_RANGES["max_steps"]
        if not (min_steps <= config.max_steps <= max_steps):
            result.add_error(
                f"max_steps must be between {min_steps} and {max_steps}, "
                f"got {config.max_steps}"
            )

        # browser_type
        valid_browsers = ["chromium", "firefox", "webkit"]
        if config.browser_type not in valid_browsers:
            result.add_error(
                f"Invalid browser_type '{config.browser_type}'. "
                f"Valid options: {', '.join(valid_browsers)}"
            )

        # headless (must be bool)
        if not isinstance(config.headless, bool):
            result.add_warning(
                f"headless should be boolean, got {type(config.headless).__name__}"
            )

    def _validate_paths(self, config: Config, result: ValidationResult) -> None:
        """Validate path configurations."""
        download_dir = Path(config.download_dir)

        # Check if download_dir is absolute or relative
        if not download_dir.is_absolute():
            # Relative paths are allowed but warn
            result.add_warning(
                f"download_dir '{config.download_dir}' is relative. "
                "Consider using an absolute path for clarity."
            )

        # Try to create download directory if it doesn't exist
        try:
            download_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            result.add_error(
                f"Cannot create download directory '{config.download_dir}': Permission denied"
            )
        except Exception as e:
            result.add_error(
                f"Cannot create download directory '{config.download_dir}': {e}"
            )

    def _validate_api_keys(self, config: Config, result: ValidationResult) -> None:
        """Validate API keys for cloud providers."""
        provider = config.default_provider

        # Ollama doesn't need an API key
        if provider == "ollama":
            return

        provider_config = getattr(config, provider, None)
        if not provider_config:
            result.add_error(f"Missing configuration for provider '{provider}'")
            return

        api_key = provider_config.api_key

        # Check if API key is set
        if not api_key:
            result.add_error(
                f"API key required for provider '{provider}'. "
                f"Set it with 'blackreach config' or environment variable."
            )
            return

        # Check API key format (basic validation)
        pattern = self.API_KEY_PATTERNS.get(provider)
        if pattern and not pattern.match(api_key):
            result.add_warning(
                f"API key for '{provider}' doesn't match expected format. "
                "It may still be valid, but please verify."
            )

    def _validate_model(self, config: Config, result: ValidationResult) -> None:
        """Validate model selection."""
        provider = config.default_provider
        if provider not in AVAILABLE_MODELS:
            return  # Already reported in provider validation

        provider_config = getattr(config, provider, None)
        if not provider_config:
            return

        model = provider_config.default_model
        if not model:
            result.add_warning(
                f"No default model set for '{provider}'. "
                f"Available models: {', '.join(AVAILABLE_MODELS[provider][:3])}..."
            )
            return

        # Check if model is in known models (warning only, could be custom)
        known_models = AVAILABLE_MODELS.get(provider, [])
        if model not in known_models:
            result.add_warning(
                f"Model '{model}' not in known models for '{provider}'. "
                f"It may be a custom model or a typo."
            )

    def validate_for_run(self, config: Config, provider: str = None, model: str = None) -> ValidationResult:
        """
        Validate configuration for an actual agent run.

        This is stricter than general validation - ensures everything
        needed for a run is properly configured.

        Args:
            config: Config object
            provider: Override provider to use
            model: Override model to use

        Returns:
            ValidationResult
        """
        result = ValidationResult(valid=True)

        use_provider = provider or config.default_provider
        provider_config = getattr(config, use_provider, None)
        use_model = model or (provider_config.default_model if provider_config else None)

        # Must have a valid provider
        if use_provider not in AVAILABLE_MODELS:
            result.add_error(f"Invalid provider: {use_provider}")
            return result

        # Must have API key for cloud providers
        if use_provider != "ollama":
            if not provider_config or not provider_config.api_key:
                result.add_error(
                    f"No API key configured for {use_provider}. "
                    f"Run 'blackreach config' to set it up."
                )

        # Must have a model
        if not use_model:
            result.add_error(
                f"No model specified for {use_provider}. "
                f"Run 'blackreach config' to set a default model."
            )

        # Validate max_steps
        if config.max_steps < 1:
            result.add_error("max_steps must be at least 1")

        return result


def validate_config(config: Config = None) -> ValidationResult:
    """
    Convenience function to validate configuration.

    Args:
        config: Config to validate, or None to load and validate current config

    Returns:
        ValidationResult with errors and warnings
    """
    if config is None:
        config = config_manager.load()

    validator = ConfigValidator()
    return validator.validate(config)


def validate_for_run(provider: str = None, model: str = None) -> ValidationResult:
    """
    Validate configuration is ready for an agent run.

    Args:
        provider: Override provider
        model: Override model

    Returns:
        ValidationResult
    """
    config = config_manager.load()
    validator = ConfigValidator()
    return validator.validate_for_run(config, provider, model)


# Global config manager instance
config_manager = ConfigManager()
