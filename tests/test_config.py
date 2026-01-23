"""
Unit tests for blackreach/config.py

Tests configuration loading, saving, and validation.
"""

import pytest
import tempfile
from pathlib import Path
from blackreach.config import (
    Config,
    ProviderConfig,
    ConfigManager,
    AVAILABLE_MODELS,
)


class TestProviderConfig:
    """Tests for provider configuration."""

    def test_default_values(self):
        """ProviderConfig has sensible defaults."""
        config = ProviderConfig()
        assert config.api_key == ""
        assert config.default_model == ""

    def test_custom_values(self):
        """ProviderConfig accepts custom values."""
        config = ProviderConfig(api_key="test-key", default_model="test-model")
        assert config.api_key == "test-key"
        assert config.default_model == "test-model"


class TestConfig:
    """Tests for main Config class."""

    def test_default_provider(self):
        """Config has default provider set."""
        config = Config()
        assert config.default_provider in ["anthropic", "openai", "google", "ollama", "xai"]

    def test_max_steps_default(self):
        """Config has sensible max_steps default."""
        config = Config()
        assert config.max_steps > 0
        assert config.max_steps <= 100

    def test_download_dir_default(self):
        """Config has download directory set."""
        config = Config()
        assert config.download_dir != ""

    def test_headless_default(self):
        """Config has headless mode default."""
        config = Config()
        assert isinstance(config.headless, bool)

    def test_has_anthropic_config(self):
        """Config has anthropic provider config."""
        config = Config()
        assert hasattr(config, 'anthropic')
        assert isinstance(config.anthropic, ProviderConfig)

    def test_has_openai_config(self):
        """Config has openai provider config."""
        config = Config()
        assert hasattr(config, 'openai')
        assert isinstance(config.openai, ProviderConfig)

    def test_has_ollama_config(self):
        """Config has ollama provider config."""
        config = Config()
        assert hasattr(config, 'ollama')
        assert isinstance(config.ollama, ProviderConfig)


class TestAvailableModels:
    """Tests for available models registry."""

    def test_has_anthropic(self):
        """AVAILABLE_MODELS includes Anthropic."""
        assert "anthropic" in AVAILABLE_MODELS

    def test_has_openai(self):
        """AVAILABLE_MODELS includes OpenAI."""
        assert "openai" in AVAILABLE_MODELS

    def test_has_ollama(self):
        """AVAILABLE_MODELS includes Ollama."""
        assert "ollama" in AVAILABLE_MODELS

    def test_models_are_lists(self):
        """Model lists are proper lists."""
        for provider, models in AVAILABLE_MODELS.items():
            assert isinstance(models, list)
            assert len(models) > 0


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_has_api_key_false_when_empty(self):
        """has_api_key returns False when key is empty."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.anthropic.api_key = ""
        assert not manager.has_api_key("anthropic")

    def test_has_api_key_true_when_set(self):
        """has_api_key returns True when key is set."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.anthropic.api_key = "test-key"
        assert manager.has_api_key("anthropic")

    def test_get_api_key_returns_key(self):
        """get_api_key returns the stored key."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.openai.api_key = "my-api-key"
        assert manager.get_api_key("openai") == "my-api-key"

    def test_get_api_key_returns_empty_for_unknown(self):
        """get_api_key returns empty string for unknown provider."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        assert manager.get_api_key("unknown_provider") == ""
