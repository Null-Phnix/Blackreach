"""
Blackreach - Autonomous Browser Agent

A general-purpose web agent that takes natural language goals
and accomplishes them through autonomous browsing.
"""

from blackreach.agent import Agent, AgentConfig, AgentCallbacks
from blackreach.memory import SessionMemory, PersistentMemory
from blackreach.llm import LLM, LLMConfig
from blackreach.browser import Hand, ProxyConfig, ProxyType, ProxyRotator
from blackreach.observer import Eyes
from blackreach.captcha_detect import (
    CaptchaDetector, CaptchaDetectionResult, CaptchaProvider,
    detect_captcha, is_captcha_present, get_captcha_detector
)
from blackreach.cookie_manager import (
    CookieManager, Cookie, CookieProfile,
    get_cookie_manager, reset_cookie_manager
)
from blackreach.knowledge import reason_about_goal, CONTENT_SOURCES
from blackreach.nav_context import NavigationContext, PageValue
from blackreach.site_handlers import get_handler_for_url, SiteHandler
from blackreach.search_intel import SearchIntelligence, get_search_intel
from blackreach.content_verify import (
    ContentVerifier, VerificationStatus, get_verifier,
    compute_hash, compute_md5, compute_checksums, compute_file_checksums,
    verify_checksum, IntegrityVerifier, IntegrityResult, get_integrity_verifier
)
from blackreach.download_history import (
    DownloadHistory, DownloadSource, HistoryEntry, DuplicateInfo, get_download_history
)
from blackreach.metadata_extract import (
    MetadataExtractor, PDFMetadata, EPUBMetadata, ImageMetadata, FileMetadata,
    ExtractionResult, MetadataType, compute_checksum, extract_pdf_metadata,
    extract_epub_metadata, get_metadata_extractor
)
from blackreach.retry_strategy import RetryManager, RetryDecision, get_retry_manager
from blackreach.timeout_manager import TimeoutManager, get_timeout_manager
from blackreach.rate_limiter import RateLimiter, get_rate_limiter
from blackreach.session_manager import SessionManager, SessionStatus, get_session_manager
from blackreach.multi_tab import SyncTabManager, TabStatus
from blackreach.download_queue import DownloadQueue, DownloadPriority, get_download_queue
from blackreach.task_scheduler import TaskScheduler, TaskPriority, get_scheduler
from blackreach.cache import PageCache, ResultCache, get_page_cache, get_result_cache
from blackreach.api import BlackreachAPI, browse, download, search, BrowseResult
from blackreach.config import (
    Config, ProviderConfig, ConfigManager, config_manager, AVAILABLE_MODELS,
    validate_config, validate_for_run, ValidationResult, ConfigValidator
)
from blackreach.parallel_ops import (
    ParallelFetcher, ParallelDownloader, ParallelSearcher,
    ParallelOperationManager, ParallelResult, ParallelTask,
    get_parallel_manager
)
from blackreach.logging import (
    SessionLogger, LogLevel, LogEntry,
    get_recent_logs, read_log, cleanup_old_logs, get_logger,
    filter_logs_by_level, get_log_summary, search_logs, get_error_logs
)
from blackreach.progress import (
    DownloadProgressTracker, TaskProgressTracker, DownloadInfo, DownloadState,
    track_downloads, format_size, format_speed, format_time
)

__version__ = "4.2.0-beta.2"
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentCallbacks",
    "SessionMemory",
    "PersistentMemory",
    "LLM",
    "LLMConfig",
    "Hand",
    "ProxyConfig",
    "ProxyType",
    "ProxyRotator",
    "Eyes",
    # CAPTCHA detection
    "CaptchaDetector",
    "CaptchaDetectionResult",
    "CaptchaProvider",
    "detect_captcha",
    "is_captcha_present",
    "get_captcha_detector",
    # Cookie management
    "CookieManager",
    "Cookie",
    "CookieProfile",
    "get_cookie_manager",
    "reset_cookie_manager",
    "reason_about_goal",
    "CONTENT_SOURCES",
    "NavigationContext",
    "PageValue",
    "get_handler_for_url",
    "SiteHandler",
    "SearchIntelligence",
    "get_search_intel",
    "ContentVerifier",
    "VerificationStatus",
    "get_verifier",
    "compute_hash",
    "compute_md5",
    "compute_checksums",
    "compute_file_checksums",
    "verify_checksum",
    "IntegrityVerifier",
    "IntegrityResult",
    "get_integrity_verifier",
    "DownloadHistory",
    "DownloadSource",
    "HistoryEntry",
    "DuplicateInfo",
    "get_download_history",
    "MetadataExtractor",
    "PDFMetadata",
    "EPUBMetadata",
    "ImageMetadata",
    "FileMetadata",
    "ExtractionResult",
    "MetadataType",
    "compute_checksum",
    "extract_pdf_metadata",
    "extract_epub_metadata",
    "get_metadata_extractor",
    "RetryManager",
    "RetryDecision",
    "get_retry_manager",
    "TimeoutManager",
    "get_timeout_manager",
    "RateLimiter",
    "get_rate_limiter",
    "SessionManager",
    "SessionStatus",
    "get_session_manager",
    "SyncTabManager",
    "TabStatus",
    "DownloadQueue",
    "DownloadPriority",
    "get_download_queue",
    "TaskScheduler",
    "TaskPriority",
    "get_scheduler",
    "PageCache",
    "ResultCache",
    "get_page_cache",
    "get_result_cache",
    "BlackreachAPI",
    "browse",
    "download",
    "search",
    "BrowseResult",
    "Config",
    "ProviderConfig",
    "ConfigManager",
    "config_manager",
    "AVAILABLE_MODELS",
    "ParallelFetcher",
    "ParallelDownloader",
    "ParallelSearcher",
    "ParallelOperationManager",
    "ParallelResult",
    "ParallelTask",
    "get_parallel_manager",
    # Config validation
    "validate_config",
    "validate_for_run",
    "ValidationResult",
    "ConfigValidator",
    # Logging
    "SessionLogger",
    "LogLevel",
    "LogEntry",
    "get_recent_logs",
    "read_log",
    "cleanup_old_logs",
    "get_logger",
    "filter_logs_by_level",
    "get_log_summary",
    "search_logs",
    "get_error_logs",
    # Progress tracking
    "DownloadProgressTracker",
    "TaskProgressTracker",
    "DownloadInfo",
    "DownloadState",
    "track_downloads",
    "format_size",
    "format_speed",
    "format_time",
]
