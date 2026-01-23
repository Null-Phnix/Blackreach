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


class TestConfigManagerMethods:
    """Tests for ConfigManager methods with file operations."""

    def test_config_to_dict_structure(self):
        """_config_to_dict returns proper structure."""
        manager = ConfigManager.__new__(ConfigManager)
        config = Config()
        config.default_provider = "openai"
        config.openai.api_key = "test-key"
        config.max_steps = 50

        result = manager._config_to_dict(config)

        assert "default_provider" in result
        assert "providers" in result
        assert "agent" in result
        assert result["default_provider"] == "openai"
        assert result["providers"]["openai"]["api_key"] == "test-key"
        assert result["agent"]["max_steps"] == 50

    def test_dict_to_config_conversion(self):
        """_dict_to_config converts dict to Config."""
        manager = ConfigManager.__new__(ConfigManager)
        data = {
            "default_provider": "anthropic",
            "providers": {
                "anthropic": {"api_key": "test-key", "default_model": "claude-3"}
            },
            "agent": {"max_steps": 100, "headless": True},
            "ui": {"verbose": False}
        }

        config = manager._dict_to_config(data)

        assert config.default_provider == "anthropic"
        assert config.anthropic.api_key == "test-key"
        assert config.max_steps == 100
        assert config.headless is True

    def test_dict_to_config_handles_missing_fields(self):
        """_dict_to_config handles missing fields gracefully."""
        manager = ConfigManager.__new__(ConfigManager)
        data = {}

        config = manager._dict_to_config(data)

        assert config.default_provider == "ollama"  # Default
        assert isinstance(config.openai, ProviderConfig)

    def test_get_current_provider(self):
        """get_current_provider returns default provider."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.default_provider = "google"

        assert manager.get_current_provider() == "google"


class TestConfigValidation:
    """Tests for config validation."""

    def test_has_google_config(self):
        """Config has google provider config."""
        config = Config()
        assert hasattr(config, 'google')
        assert isinstance(config.google, ProviderConfig)

    def test_has_xai_config(self):
        """Config has xai provider config."""
        config = Config()
        assert hasattr(config, 'xai')
        assert isinstance(config.xai, ProviderConfig)

    def test_provider_config_has_base_url(self):
        """ProviderConfig has base_url field."""
        config = ProviderConfig()
        assert hasattr(config, 'base_url')

    def test_config_has_verbose(self):
        """Config has verbose setting."""
        config = Config()
        assert hasattr(config, 'verbose')
        assert isinstance(config.verbose, bool)

    def test_config_has_show_thinking(self):
        """Config has show_thinking setting."""
        config = Config()
        assert hasattr(config, 'show_thinking')
        assert isinstance(config.show_thinking, bool)


class TestAvailableModelsContent:
    """Tests for available models content."""

    def test_has_google(self):
        """AVAILABLE_MODELS includes Google."""
        assert "google" in AVAILABLE_MODELS

    def test_has_xai(self):
        """AVAILABLE_MODELS includes xAI."""
        assert "xai" in AVAILABLE_MODELS

    def test_anthropic_has_claude_models(self):
        """Anthropic has Claude models."""
        models = AVAILABLE_MODELS.get("anthropic", [])
        model_str = " ".join(models).lower()
        assert "claude" in model_str

    def test_openai_has_gpt_models(self):
        """OpenAI has GPT models."""
        models = AVAILABLE_MODELS.get("openai", [])
        model_str = " ".join(models).lower()
        assert "gpt" in model_str

    def test_ollama_has_local_models(self):
        """Ollama has local model options."""
        models = AVAILABLE_MODELS.get("ollama", [])
        assert len(models) > 0


class TestConfigManagerFileOps:
    """Tests for ConfigManager file operations."""

    def test_load_config_creates_default(self, tmp_path, monkeypatch):
        """load() creates default config if file doesn't exist."""
        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        config = manager.load()

        assert config is not None
        assert isinstance(config, Config)
        assert config_file.exists()  # File was created

    def test_load_config_from_existing_file(self, tmp_path, monkeypatch):
        """load() reads config from existing file."""
        import yaml

        config_file = tmp_path / "config.yml"
        data = {
            "default_provider": "openai",
            "providers": {"openai": {"api_key": "test-key"}},
            "agent": {"max_steps": 50},
            "ui": {"verbose": True}
        }
        with open(config_file, 'w') as f:
            yaml.dump(data, f)

        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        config = manager.load()

        assert config.default_provider == "openai"
        assert config.max_steps == 50

    def test_load_env_keys(self, monkeypatch):
        """_load_env_keys() loads API keys from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic-key")

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._load_env_keys()

        assert manager._config.openai.api_key == "env-openai-key"
        assert manager._config.anthropic.api_key == "env-anthropic-key"

    def test_save_config(self, tmp_path, monkeypatch):
        """save() writes config to file."""
        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.default_provider = "google"
        manager._config.max_steps = 75

        manager.save()

        assert config_file.exists()
        # Verify file content
        import yaml
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["default_provider"] == "google"
        assert data["agent"]["max_steps"] == 75

    def test_save_creates_default_config_when_none(self, tmp_path, monkeypatch):
        """save() creates default config when _config is None."""
        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None  # No config loaded

        manager.save()

        assert config_file.exists()

    def test_load_env_keys_returns_when_no_config(self):
        """_load_env_keys returns early when _config is None."""
        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        # Should not raise
        manager._load_env_keys()

    def test_load_handles_corrupt_config_file(self, tmp_path, monkeypatch):
        """load() handles corrupt config file gracefully."""
        config_file = tmp_path / "config.yml"
        # Write invalid YAML
        with open(config_file, 'w') as f:
            f.write("{{{{invalid yaml content::::")

        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        config = manager.load()

        # Should return default config
        assert config is not None
        assert isinstance(config, Config)


class TestConfigManagerSetters:
    """Tests for ConfigManager setter methods."""

    def test_set_api_key_valid_provider(self, tmp_path, monkeypatch):
        """set_api_key sets key for valid provider."""
        from blackreach.config import ConfigManager

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        manager.set_api_key("openai", "test-api-key")

        assert manager._config.openai.api_key == "test-api-key"

    def test_set_api_key_invalid_provider(self, tmp_path, monkeypatch):
        """set_api_key raises for invalid provider."""
        from blackreach.config import ConfigManager
        from blackreach.exceptions import InvalidConfigError

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        with pytest.raises(InvalidConfigError):
            manager.set_api_key("invalid_provider", "key")

    def test_set_default_provider_valid(self, tmp_path, monkeypatch):
        """set_default_provider sets valid provider."""
        from blackreach.config import ConfigManager

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        manager.set_default_provider("openai")

        assert manager._config.default_provider == "openai"

    def test_set_default_provider_invalid(self, tmp_path, monkeypatch):
        """set_default_provider raises for invalid provider."""
        from blackreach.config import ConfigManager
        from blackreach.exceptions import InvalidConfigError

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        with pytest.raises(InvalidConfigError):
            manager.set_default_provider("invalid_provider")

    def test_set_default_model_valid(self, tmp_path, monkeypatch):
        """set_default_model sets model for valid provider."""
        from blackreach.config import ConfigManager

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        manager.set_default_model("openai", "gpt-4o")

        assert manager._config.openai.default_model == "gpt-4o"

    def test_set_default_model_invalid_provider(self, tmp_path, monkeypatch):
        """set_default_model raises for invalid provider."""
        from blackreach.config import ConfigManager
        from blackreach.exceptions import InvalidConfigError

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = None

        with pytest.raises(InvalidConfigError):
            manager.set_default_model("invalid_provider", "model")

    def test_get_current_model(self, tmp_path, monkeypatch):
        """get_current_model returns model for current provider."""
        from blackreach.config import ConfigManager

        config_file = tmp_path / "config.yml"
        monkeypatch.setattr("blackreach.config.CONFIG_FILE", config_file)

        manager = ConfigManager.__new__(ConfigManager)
        manager._config = Config()
        manager._config.default_provider = "anthropic"
        manager._config.anthropic.default_model = "claude-3"

        model = manager.get_current_model()

        assert model == "claude-3"
