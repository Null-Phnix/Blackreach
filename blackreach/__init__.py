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

__version__ = "2.1.0"
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
]
