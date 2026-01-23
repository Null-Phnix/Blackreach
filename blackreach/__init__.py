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

__version__ = "0.3.0"
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
]
