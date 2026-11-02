"""
Blackreach - Autonomous Browser Agent

A general-purpose web agent that takes natural language goals
and accomplishes them through autonomous browsing.

Performance: Uses lazy imports to speed up package load time.
Only imports modules when their symbols are first accessed.
"""

from typing import TYPE_CHECKING

__version__ = "5.0.0-beta.3"

# Mapping of exported names to their source modules
# Format: "ExportedName": ("module_path", "original_name" or None for same name)
_LAZY_IMPORTS = {
    # Core agent
    "Agent": ("blackreach.agent", None),
    "AgentConfig": ("blackreach.agent", None),
    "AgentCallbacks": ("blackreach.agent", None),

    # Memory
    "SessionMemory": ("blackreach.memory", None),
    "PersistentMemory": ("blackreach.memory", None),

    # LLM
    "LLM": ("blackreach.llm", None),
    "LLMConfig": ("blackreach.llm", None),

    # Browser
    "Hand": ("blackreach.browser", None),
    "ProxyConfig": ("blackreach.browser", None),
    "ProxyType": ("blackreach.browser", None),
    "ProxyRotator": ("blackreach.browser", None),

    # Observer (deprecated: replaced by dom_walker.py, kept for backward compatibility)
    "Eyes": ("blackreach.observer", None),

    # CAPTCHA detection
    "CaptchaDetector": ("blackreach.captcha_detect", None),
    "CaptchaDetectionResult": ("blackreach.captcha_detect", None),
    "CaptchaProvider": ("blackreach.captcha_detect", None),
    "detect_captcha": ("blackreach.captcha_detect", None),
    "is_captcha_present": ("blackreach.captcha_detect", None),
    "get_captcha_detector": ("blackreach.captcha_detect", None),

    # Cookie management
    "CookieManager": ("blackreach.cookie_manager", None),
    "Cookie": ("blackreach.cookie_manager", None),
    "CookieProfile": ("blackreach.cookie_manager", None),
    "get_cookie_manager": ("blackreach.cookie_manager", None),
    "reset_cookie_manager": ("blackreach.cookie_manager", None),

    # Knowledge
    "reason_about_goal": ("blackreach.knowledge", None),
    "CONTENT_SOURCES": ("blackreach.knowledge", None),

    # Navigation
    "NavigationContext": ("blackreach.nav_context", None),
    "PageValue": ("blackreach.nav_context", None),

    # Site handlers
    "get_handler_for_url": ("blackreach.site_handlers", None),
    "SiteHandler": ("blackreach.site_handlers", None),

    # Search intelligence
    "SearchIntelligence": ("blackreach.search_intel", None),
    "get_search_intel": ("blackreach.search_intel", None),

    # Content verification
    "ContentVerifier": ("blackreach.content_verify", None),
    "VerificationStatus": ("blackreach.content_verify", None),
    "get_verifier": ("blackreach.content_verify", None),
    "compute_hash": ("blackreach.content_verify", None),
    "compute_md5": ("blackreach.content_verify", None),
    "compute_checksums": ("blackreach.content_verify", None),
    "compute_file_checksums": ("blackreach.content_verify", None),
    "verify_checksum": ("blackreach.content_verify", None),
    "IntegrityVerifier": ("blackreach.content_verify", None),
    "IntegrityResult": ("blackreach.content_verify", None),
    "get_integrity_verifier": ("blackreach.content_verify", None),

    # Download history
    "DownloadHistory": ("blackreach.download_history", None),
    "DownloadSource": ("blackreach.download_history", None),
    "HistoryEntry": ("blackreach.download_history", None),
    "DuplicateInfo": ("blackreach.download_history", None),
    "get_download_history": ("blackreach.download_history", None),

    # Metadata extraction
    "MetadataExtractor": ("blackreach.metadata_extract", None),
    "PDFMetadata": ("blackreach.metadata_extract", None),
    "EPUBMetadata": ("blackreach.metadata_extract", None),
    "ImageMetadata": ("blackreach.metadata_extract", None),
    "FileMetadata": ("blackreach.metadata_extract", None),
    "ExtractionResult": ("blackreach.metadata_extract", None),
    "MetadataType": ("blackreach.metadata_extract", None),
    "compute_checksum": ("blackreach.metadata_extract", None),
    "extract_pdf_metadata": ("blackreach.metadata_extract", None),
    "extract_epub_metadata": ("blackreach.metadata_extract", None),
    "get_metadata_extractor": ("blackreach.metadata_extract", None),

    # Timeout manager
    "TimeoutManager": ("blackreach.timeout_manager", None),
    "get_timeout_manager": ("blackreach.timeout_manager", None),

    # Rate limiter
    "RateLimiter": ("blackreach.rate_limiter", None),
    "get_rate_limiter": ("blackreach.rate_limiter", None),

    # Session manager
    "SessionManager": ("blackreach.session_manager", None),
    "SessionStatus": ("blackreach.session_manager", None),
    "get_session_manager": ("blackreach.session_manager", None),

    # Multi-tab
    "SyncTabManager": ("blackreach.multi_tab", None),
    "TabStatus": ("blackreach.multi_tab", None),

    # Download queue
    "DownloadQueue": ("blackreach.download_queue", None),
    "DownloadPriority": ("blackreach.download_queue", None),
    "get_download_queue": ("blackreach.download_queue", None),

    # Task scheduler
    "TaskScheduler": ("blackreach.task_scheduler", None),
    "TaskPriority": ("blackreach.task_scheduler", None),
    "get_scheduler": ("blackreach.task_scheduler", None),

    # Cache
    "PageCache": ("blackreach.cache", None),
    "ResultCache": ("blackreach.cache", None),
    "get_page_cache": ("blackreach.cache", None),
    "get_result_cache": ("blackreach.cache", None),

    # API
    "BlackreachAPI": ("blackreach.api", None),
    "browse": ("blackreach.api", None),
    "download": ("blackreach.api", None),
    "search": ("blackreach.api", None),
    "BrowseResult": ("blackreach.api", None),

    # Config
    "Config": ("blackreach.config", None),
    "ProviderConfig": ("blackreach.config", None),
    "ConfigManager": ("blackreach.config", None),
    "config_manager": ("blackreach.config", None),
    "AVAILABLE_MODELS": ("blackreach.config", None),
    "validate_config": ("blackreach.config", None),
    "validate_for_run": ("blackreach.config", None),
    "ValidationResult": ("blackreach.config", None),
    "ConfigValidator": ("blackreach.config", None),

    # Parallel operations
    "ParallelFetcher": ("blackreach.parallel_ops", None),
    "ParallelDownloader": ("blackreach.parallel_ops", None),
    "ParallelSearcher": ("blackreach.parallel_ops", None),
    "ParallelOperationManager": ("blackreach.parallel_ops", None),
    "ParallelResult": ("blackreach.parallel_ops", None),
    "ParallelTask": ("blackreach.parallel_ops", None),
    "get_parallel_manager": ("blackreach.parallel_ops", None),

    # Logging
    "SessionLogger": ("blackreach.logging", None),
    "LogLevel": ("blackreach.logging", None),
    "LogEntry": ("blackreach.logging", None),
    "get_recent_logs": ("blackreach.logging", None),
    "read_log": ("blackreach.logging", None),
    "cleanup_old_logs": ("blackreach.logging", None),
    "get_logger": ("blackreach.logging", None),
    "filter_logs_by_level": ("blackreach.logging", None),
    "get_log_summary": ("blackreach.logging", None),
    "search_logs": ("blackreach.logging", None),
    "get_error_logs": ("blackreach.logging", None),

    # Progress tracking
    "DownloadProgressTracker": ("blackreach.progress", None),
    "TaskProgressTracker": ("blackreach.progress", None),
    "DownloadInfo": ("blackreach.progress", None),
    "DownloadState": ("blackreach.progress", None),
    "track_downloads": ("blackreach.progress", None),
    "format_size": ("blackreach.progress", None),
    "format_speed": ("blackreach.progress", None),
    "format_time": ("blackreach.progress", None),
}

# Cache for already-imported objects
_import_cache = {}


def __getattr__(name: str):
    """
    Lazy import mechanism using module-level __getattr__ (PEP 562).

    This defers the actual import until the attribute is first accessed,
    dramatically reducing package load time from ~2-3 seconds to ~0.1 seconds.
    """
    if name in _import_cache:
        return _import_cache[name]

    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        attr_name = attr_name or name

        import importlib
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)

        # Cache the imported value
        _import_cache[name] = value
        globals()[name] = value  # Also add to globals for faster subsequent access

        return value

    raise AttributeError(f"module 'blackreach' has no attribute '{name}'")


def __dir__():
    """Return list of available names for tab-completion and dir()."""
    return list(_LAZY_IMPORTS.keys()) + ["__version__"]


__all__ = list(_LAZY_IMPORTS.keys())


# TYPE_CHECKING block for IDE support - these imports only happen
# during static analysis, not at runtime
if TYPE_CHECKING:
    from blackreach.agent import Agent, AgentCallbacks, AgentConfig
    from blackreach.api import BlackreachAPI, BrowseResult, browse, download, search
    from blackreach.browser import Hand, ProxyConfig, ProxyRotator, ProxyType
    from blackreach.cache import PageCache, ResultCache, get_page_cache, get_result_cache
    from blackreach.captcha_detect import (
        CaptchaDetectionResult,
        CaptchaDetector,
        CaptchaProvider,
        detect_captcha,
        get_captcha_detector,
        is_captcha_present,
    )
    from blackreach.config import (
        AVAILABLE_MODELS,
        Config,
        ConfigManager,
        ConfigValidator,
        ProviderConfig,
        ValidationResult,
        config_manager,
        validate_config,
        validate_for_run,
    )
    from blackreach.content_verify import (
        ContentVerifier,
        IntegrityResult,
        IntegrityVerifier,
        VerificationStatus,
        compute_checksums,
        compute_file_checksums,
        compute_hash,
        compute_md5,
        get_integrity_verifier,
        get_verifier,
        verify_checksum,
    )
    from blackreach.cookie_manager import (
        Cookie,
        CookieManager,
        CookieProfile,
        get_cookie_manager,
        reset_cookie_manager,
    )
    from blackreach.download_history import (
        DownloadHistory,
        DownloadSource,
        DuplicateInfo,
        HistoryEntry,
        get_download_history,
    )
    from blackreach.download_queue import DownloadPriority, DownloadQueue, get_download_queue
    from blackreach.knowledge import CONTENT_SOURCES, reason_about_goal
    from blackreach.llm import LLM, LLMConfig
    from blackreach.logging import (
        LogEntry,
        LogLevel,
        SessionLogger,
        cleanup_old_logs,
        filter_logs_by_level,
        get_error_logs,
        get_log_summary,
        get_logger,
        get_recent_logs,
        read_log,
        search_logs,
    )
    from blackreach.memory import PersistentMemory, SessionMemory
    from blackreach.metadata_extract import (
        EPUBMetadata,
        ExtractionResult,
        FileMetadata,
        ImageMetadata,
        MetadataExtractor,
        MetadataType,
        PDFMetadata,
        compute_checksum,
        extract_epub_metadata,
        extract_pdf_metadata,
        get_metadata_extractor,
    )
    from blackreach.multi_tab import SyncTabManager, TabStatus
    from blackreach.nav_context import NavigationContext, PageValue
    from blackreach.observer import Eyes  # Deprecated: use dom_walker instead
    from blackreach.parallel_ops import (
        ParallelDownloader,
        ParallelFetcher,
        ParallelOperationManager,
        ParallelResult,
        ParallelSearcher,
        ParallelTask,
        get_parallel_manager,
    )
    from blackreach.progress import (
        DownloadInfo,
        DownloadProgressTracker,
        DownloadState,
        TaskProgressTracker,
        format_size,
        format_speed,
        format_time,
        track_downloads,
    )
    from blackreach.rate_limiter import RateLimiter, get_rate_limiter
    from blackreach.search_intel import SearchIntelligence, get_search_intel
    from blackreach.session_manager import SessionManager, SessionStatus, get_session_manager
    from blackreach.site_handlers import SiteHandler, get_handler_for_url
    from blackreach.task_scheduler import TaskPriority, TaskScheduler, get_scheduler
    from blackreach.timeout_manager import TimeoutManager, get_timeout_manager
