"""Tests for agent adaptive routing and domain skills wiring."""

from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from blackreach.agent import Agent, AgentConfig
from blackreach.adaptive_browser import BrowserMode, RoutePlan, BrowserRouter
from blackreach.bulk_fetcher import FetchResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent(monkeypatch):
    """Agent with mocks for all heavy dependencies."""
    monkeypatch.setenv('OLLAMA_MODEL', 'hf.co/...')
    monkeypatch.setenv('OLLAMA_HOST', 'http://localhost:11434')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')

    cfg = AgentConfig(use_adaptive=True)
    a = Agent(agent_config=cfg)
    # Mocks for browser
    a.hand = MagicMock()
    a.hand.page = MagicMock()
    a.hand.get_url.return_value = "https://example.com"
    a.hand.get_title.return_value = "Example"
    a.hand.is_awake = True
    # Mocks for router + skills
    a._router = MagicMock()
    a._skill_manager = MagicMock()
    a._skill_manager.get_selector.return_value = None
    a._skill_manager.record_success = MagicMock()
    a._skill_manager.record_failure = MagicMock()
    return a


# ---------------------------------------------------------------------------
# _navigate_with_scan
# ---------------------------------------------------------------------------

class TestNavigateWithScan:

    def test_when_adaptive_disabled_uses_plain_goto(self, agent):
        agent.config.use_adaptive = False
        agent._navigate_with_scan('https://example.com')
        agent.hand.goto.assert_called_once_with('https://example.com')

    def test_lightweight_uses_bulk_fetcher_then_set_content(self, agent):
        plan = RoutePlan(
            url='https://wikipedia.org/wiki/Python',
            mode=BrowserMode.LIGHTWEIGHT,
            confidence=0.15,
            reasons=['known-light-domain'],
            estimated_cost_ms=200,
        )
        agent._router.plan_for.return_value = plan

        fake_result = FetchResult(
            url='https://wikipedia.org/wiki/Python',
            status=200,
            html='<html><title>Python</title></html>',
            elapsed_ms=145.0,
        )

        with patch('blackreach.bulk_fetcher.BulkFetcher') as MockFetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch.return_value = fake_result
            mock_fetcher.__enter__ = MagicMock(return_value=mock_fetcher)
            mock_fetcher.__exit__ = MagicMock(return_value=False)
            MockFetcher.return_value = mock_fetcher

            agent._navigate_with_scan('https://wikipedia.org/wiki/Python')

        agent.hand.page.set_content.assert_called_once()

    def test_lightweight_falls_back_on_fetch_fail(self, agent):
        plan = RoutePlan(
            url='https://wikipedia.org/wiki/Python', mode=BrowserMode.LIGHTWEIGHT,
            confidence=0.15, reasons=[], estimated_cost_ms=200,
        )
        agent._router.plan_for.return_value = plan

        fake_result = FetchResult(
            url='https://wikipedia.org/wiki/Python',
            status=0,
            html='',
            error='timeout',
            elapsed_ms=5000,
        )

        with patch('blackreach.bulk_fetcher.BulkFetcher') as MockFetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch.return_value = fake_result
            mock_fetcher.__enter__ = MagicMock(return_value=mock_fetcher)
            mock_fetcher.__exit__ = MagicMock(return_value=False)
            MockFetcher.return_value = mock_fetcher

            agent._navigate_with_scan('https://wikipedia.org/wiki/Python')

        agent.hand.goto.assert_called_once_with('https://wikipedia.org/wiki/Python')

    def test_full_stealth_uses_plain_goto(self, agent):
        plan = RoutePlan(
            url='https://linkedin.com', mode=BrowserMode.FULL_STEALTH,
            confidence=0.85, reasons=['known-hard-site'], estimated_cost_ms=20000,
        )
        agent._router.plan_for.return_value = plan
        agent._navigate_with_scan('https://linkedin.com')
        agent.hand.goto.assert_called_once_with('https://linkedin.com')


# ---------------------------------------------------------------------------
# _try_skill_click
# ---------------------------------------------------------------------------

class TestTrySkillClick:

    def test_returns_none_when_no_skill(self, agent):
        agent._skill_manager.get_selector.return_value = None
        assert agent._try_skill_click('example.com', 'search') is None

    def test_returns_result_on_success(self, agent):
        agent._skill_manager.get_selector.return_value = 'input[name="q"]'
        result = agent._try_skill_click('example.com', 'search')
        assert result == {'action': 'click', 'skill': 'search', 'selector': 'input[name="q"]'}
        agent._skill_manager.record_success.assert_called_once()

    def test_records_failure_on_click_error(self, agent):
        agent._skill_manager.get_selector.return_value = 'input[name="q"]'
        agent.hand.click.side_effect = Exception("element not found")
        result = agent._try_skill_click('example.com', 'search')
        assert result is None
        agent._skill_manager.record_failure.assert_called_once()


# ---------------------------------------------------------------------------
# _record_skill
# ---------------------------------------------------------------------------

class TestRecordSkill:

    def test_records_success_correctly(self, agent):
        agent._record_skill('github.com', 'click', 5, '[data-br-id="5"]', True)
        agent._skill_manager.record_success.assert_called_once()

    def test_records_failure_correctly(self, agent):
        agent._record_skill('github.com', 'click', 5, '[data-br-id="5"]', False, 'timeout')
        agent._skill_manager.record_failure.assert_called_once()

    def test_no_op_when_skill_manager_disabled(self, agent):
        agent._skill_manager = None
        agent._record_skill('github.com', 'click', 5, None, True)
        # just shouldn't raise

    def test_no_op_when_domain_empty(self, agent):
        agent._record_skill('', 'click', 5, None, True)
        agent._skill_manager.record_success.assert_not_called()


# ---------------------------------------------------------------------------
# Click action wiring
# ---------------------------------------------------------------------------

class TestClickWiring:

    def test_skill_tried_before_element_id(self, agent):
        """Skill-0 should run before element ID discovery."""
        agent._skill_manager.get_selector.return_value = 'nav button'

        result = agent._execute_action('click', {
            '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
        })
        assert result['selector'] == 'nav button'
        agent._skill_manager.record_success.assert_called()

    def test_element_id_recorded_on_success(self, agent):
        agent._skill_manager.get_selector.return_value = None
        loc = MagicMock()
        loc.count.return_value = 1
        agent.hand.page.locator.return_value = loc

        result = agent._execute_action('click', {
            '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
        })
        assert result['element'] == 3
        agent._skill_manager.record_success.assert_called()

    def test_skill_failure_recorded_on_click_error(self, agent):
        agent._skill_manager.get_selector.return_value = None
        loc = MagicMock()
        loc.count.return_value = 0
        agent.hand.page.locator.return_value = loc

        with pytest.raises(Exception):
            agent._execute_action('click', {
                '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
            })
        # Should record failure
        agent._skill_manager.record_failure.assert_called()

    def test_navigate_routed_through_scan(self, agent):
        """navigate action should use _navigate_with_scan."""
        plan = RoutePlan(
            url='https://newsite.com', mode=BrowserMode.FULL_STEALTH,
            confidence=0.8, reasons=[], estimated_cost_ms=20000,
        )
        agent._router.plan_for.return_value = plan

        result = agent._execute_action('navigate', {'url': 'https://newsite.com'})
        assert result['action'] == 'navigate'
        agent._router.plan_for.assert_called_once()


# ---------------------------------------------------------------------------
# Skill action integration in _execute_action
# ---------------------------------------------------------------------------

class TestSkillIntegration:

    def test_try_skill_click_called_before_element_id(self, agent):
        agent._skill_manager.get_selector.return_value = 'nav button'
        result = agent._execute_action('click', {
            '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
        })
        assert result['selector'] == 'nav button'

    def test_record_skill_called_on_success(self, agent):
        agent._skill_manager.get_selector.return_value = None
        loc = MagicMock()
        loc.count.return_value = 1
        agent.hand.page.locator.return_value = loc

        agent._execute_action('click', {
            '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
        })
        agent._skill_manager.record_success.assert_called()

    def test_record_skill_called_on_failure(self, agent):
        agent._skill_manager.get_selector.return_value = None
        loc = MagicMock()
        loc.count.return_value = 0
        agent.hand.page.locator.return_value = loc

        with pytest.raises(Exception):
            agent._execute_action('click', {
                '_element_id': 3, 'selector': '', 'text': '', '_thought': ''
            })
        agent._skill_manager.record_failure.assert_called()
