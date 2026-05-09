"""Regression tests for mixin-level import bugs."""
import pytest


def test_agent_actions_has_searchengine_import():
    """Regression: SearchEngine was referenced in agent_actions.py but only
    imported in agent.py. After mixin split, it was unbound there.
    This test verifies the fix by importing agent_actions in isolation."""
    from blackreach import agent_actions

    assert hasattr(agent_actions, "SearchEngine")
    assert hasattr(agent_actions, "get_search_fallback_url")

    # Verify we can actually compare against SearchEngine members
    from blackreach.search_intel import SearchEngine
    assert agent_actions.SearchEngine is SearchEngine
    assert SearchEngine.GOOGLE != SearchEngine.DUCKDUCKGO


def test_agent_actions_navigate_references_searchengine():
    """Verify the navigate action handler references search fallback logic.

    The original bug was `SearchEngine` used without import in agent_actions.py.
    The fix added the import and the code now uses `DEFAULT_SEARCH_ENGINE`
    (a SearchEngine constant) and `get_search_fallback_url`.
    """
    import inspect
    from blackreach import agent_actions

    src = inspect.getsource(agent_actions.AgentActionsMixin)
    # These are the actual names referenced in the navigate handler
    assert "get_search_fallback_url" in src
    assert "DEFAULT_SEARCH_ENGINE" in src
    assert "_blocked_engines" in src
