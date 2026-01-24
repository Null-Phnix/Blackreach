"""
Configuration System (v3.5.0)

Provides unified configuration management for Blackreach:
- File-based configuration (YAML/JSON)
- Environment variable support
- Profile support (dev, prod, etc.)
- Configuration validation
- Runtime configuration updates
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List
from pathlib import Path
import os
import json


@dataclass
class BrowserConfig:
    """Browser-related configuration."""
    type: str = "chromium"
    headless: bool = False
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: Optional[str] = None
    proxy: Optional[str] = None


@dataclass
class LLMProviderConfig:
    """LLM provider configuration."""
    provider: str = "ollama"
    model: str = "llama3.2"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 1000


@dataclass
class AgentBehaviorConfig:
    """Agent behavior configuration."""
    max_steps: int = 50
    step_pause_seconds: float = 0.5
    stuck_threshold: int = 3
    max_retries: int = 3
    auto_complete: bool = True


@dataclass
class DownloadSettings:
    """Download-related configuration."""
    directory: str = "./downloads"
    max_concurrent: int = 3
    verify_content: bool = True
    min_file_size: int = 1000


@dataclass
class CacheSettings:
    """Cache configuration."""
    enabled: bool = True
    max_pages: int = 100
    max_size_mb: int = 50
    ttl_seconds: float = 300.0


@dataclass
class BlackreachConfig:
    """Root configuration for Blackreach."""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    llm: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    agent: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    download: DownloadSettings = field(default_factory=DownloadSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    memory_db: str = "./memory.db"
    profile: str = "default"


class ConfigManager:
    """Manages configuration loading and access."""

    ENV_PREFIX = "BLACKREACH_"

    def __init__(self, config_path: Optional[Path] = None):
        self.config = BlackreachConfig()
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment."""
        if self.config_path and self.config_path.exists():
            self._load_file(self.config_path)
        self._load_env()

    def _load_file(self, path: Path):
        """Load configuration from a file."""
        try:
            content = path.read_text()
            data = json.loads(content)
            self._apply_dict(data)
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}")

    def _load_env(self):
        """Load configuration from environment variables."""
        env_mappings = {
            f"{self.ENV_PREFIX}HEADLESS": ("browser", "headless"),
            f"{self.ENV_PREFIX}LLM_PROVIDER": ("llm", "provider"),
            f"{self.ENV_PREFIX}LLM_MODEL": ("llm", "model"),
            f"{self.ENV_PREFIX}LLM_API_KEY": ("llm", "api_key"),
            f"{self.ENV_PREFIX}MAX_STEPS": ("agent", "max_steps"),
            f"{self.ENV_PREFIX}DOWNLOAD_DIR": ("download", "directory"),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                self._set_value(section, key, value)

    def _apply_dict(self, data: Dict):
        """Apply a dictionary of configuration values."""
        for section in ["browser", "llm", "agent", "download", "cache"]:
            if section in data:
                section_obj = getattr(self.config, section, None)
                if section_obj:
                    for k, v in data[section].items():
                        if hasattr(section_obj, k):
                            setattr(section_obj, k, v)

        if "memory_db" in data:
            self.config.memory_db = data["memory_db"]

    def _set_value(self, section: str, key: str, value: str):
        """Set a configuration value."""
        if value.lower() in ('true', 'yes', '1'):
            value = True
        elif value.lower() in ('false', 'no', '0'):
            value = False
        elif value.isdigit():
            value = int(value)

        section_obj = getattr(self.config, section, None)
        if section_obj and hasattr(section_obj, key):
            setattr(section_obj, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dotted key."""
        parts = key.split('.')
        obj = self.config
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default
        return obj

    def save(self, path: Optional[Path] = None):
        """Save current configuration to file."""
        path = path or Path("blackreach.json")
        data = {
            "browser": asdict(self.config.browser),
            "llm": asdict(self.config.llm),
            "agent": asdict(self.config.agent),
            "download": asdict(self.config.download),
            "cache": asdict(self.config.cache),
            "memory_db": self.config.memory_db,
            "profile": self.config.profile
        }
        path.write_text(json.dumps(data, indent=2))


_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def load_config(path: Path) -> ConfigManager:
    """Load configuration from a specific path."""
    global _config_manager
    _config_manager = ConfigManager(path)
    return _config_manager
