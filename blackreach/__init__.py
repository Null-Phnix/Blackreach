"""
Blackreach - Autonomous Browser Agent

A general-purpose web agent that takes natural language goals
and accomplishes them through autonomous browsing.
"""

from blackreach.agent import Agent, AgentConfig, AgentCallbacks
from blackreach.memory import SessionMemory, PersistentMemory
from blackreach.llm import LLM, LLMConfig
from blackreach.browser import Hand
from blackreach.observer import Eyes
from blackreach.knowledge import reason_about_goal, CONTENT_SOURCES
from blackreach.nav_context import NavigationContext, PageValue
from blackreach.site_handlers import get_handler_for_url, SiteHandler
from blackreach.search_intel import SearchIntelligence, get_search_intel
from blackreach.content_verify import ContentVerifier, VerificationStatus, get_verifier
from blackreach.retry_strategy import RetryManager, RetryDecision, get_retry_manager
from blackreach.timeout_manager import TimeoutManager, get_timeout_manager
from blackreach.rate_limiter import RateLimiter, get_rate_limiter
from blackreach.session_manager import SessionManager, SessionStatus, get_session_manager
from blackreach.multi_tab import SyncTabManager, TabStatus
from blackreach.download_queue import DownloadQueue, DownloadPriority, get_download_queue
from blackreach.task_scheduler import TaskScheduler, TaskPriority, get_scheduler
from blackreach.cache import PageCache, ResultCache, get_page_cache, get_result_cache
from blackreach.api import BlackreachAPI, browse, download, search, BrowseResult
from blackreach.config import Config, ProviderConfig, ConfigManager, config_manager, AVAILABLE_MODELS

__version__ = "4.0.0-beta.1"
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentCallbacks",
    "SessionMemory",
    "PersistentMemory",
    "LLM",
    "LLMConfig",
    "Hand",
    "Eyes",
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
]
