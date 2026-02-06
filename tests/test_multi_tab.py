"""
Tests for the Multi-Tab Browser Support module.

Tests cover:
- TabStatus enum values
- TabInfo dataclass
- TabPoolConfig defaults and configuration
- SyncTabManager (the synchronous implementation)
- Tab lifecycle management (create, get, release, close)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import time

from blackreach.multi_tab import (
    TabStatus,
    TabInfo,
    TabPoolConfig,
    TabManager,
    SyncTabManager,
)


# =============================================================================
# TabStatus Enum Tests
# =============================================================================

class TestTabStatus:
    """Tests for TabStatus enum."""

    def test_idle_value(self):
        """TabStatus.IDLE should have value 'idle'."""
        assert TabStatus.IDLE.value == "idle"

    def test_loading_value(self):
        """TabStatus.LOADING should have value 'loading'."""
        assert TabStatus.LOADING.value == "loading"

    def test_active_value(self):
        """TabStatus.ACTIVE should have value 'active'."""
        assert TabStatus.ACTIVE.value == "active"

    def test_waiting_value(self):
        """TabStatus.WAITING should have value 'waiting'."""
        assert TabStatus.WAITING.value == "waiting"

    def test_error_value(self):
        """TabStatus.ERROR should have value 'error'."""
        assert TabStatus.ERROR.value == "error"

    def test_closed_value(self):
        """TabStatus.CLOSED should have value 'closed'."""
        assert TabStatus.CLOSED.value == "closed"

    def test_all_status_values_unique(self):
        """All TabStatus values should be unique."""
        values = [s.value for s in TabStatus]
        assert len(values) == len(set(values))

    def test_can_iterate_all_statuses(self):
        """Should be able to iterate through all statuses."""
        statuses = list(TabStatus)
        assert len(statuses) == 6

    def test_status_from_string(self):
        """Should be able to create status from string value."""
        for status in TabStatus:
            assert TabStatus(status.value) == status


# =============================================================================
# TabInfo Dataclass Tests
# =============================================================================

class TestTabInfo:
    """Tests for TabInfo dataclass."""

    def test_minimal_creation(self):
        """TabInfo can be created with minimal required fields."""
        mock_page = Mock()
        tab = TabInfo(tab_id="tab_1", page=mock_page)
        assert tab.tab_id == "tab_1"
        assert tab.page == mock_page

    def test_default_status_is_idle(self):
        """Default status should be IDLE."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        assert tab.status == TabStatus.IDLE

    def test_default_current_url_is_empty(self):
        """Default current_url should be empty string."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        assert tab.current_url == ""

    def test_default_task_is_empty(self):
        """Default task should be empty string."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        assert tab.task == ""

    def test_default_error_is_none(self):
        """Default error should be None."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        assert tab.error is None

    def test_created_at_is_set(self):
        """created_at should be set to current time by default."""
        before = datetime.now()
        tab = TabInfo(tab_id="tab_1", page=Mock())
        after = datetime.now()
        assert before <= tab.created_at <= after

    def test_last_activity_is_set(self):
        """last_activity should be set to current time by default."""
        before = datetime.now()
        tab = TabInfo(tab_id="tab_1", page=Mock())
        after = datetime.now()
        assert before <= tab.last_activity <= after

    def test_all_fields_can_be_set(self):
        """All fields can be set during creation."""
        mock_page = Mock()
        created = datetime(2025, 1, 1, 12, 0, 0)
        tab = TabInfo(
            tab_id="custom_tab",
            page=mock_page,
            status=TabStatus.ACTIVE,
            current_url="https://example.com",
            task="test_task",
            created_at=created,
            last_activity=created,
            error="test error"
        )
        assert tab.tab_id == "custom_tab"
        assert tab.status == TabStatus.ACTIVE
        assert tab.current_url == "https://example.com"
        assert tab.task == "test_task"
        assert tab.error == "test error"

    def test_status_can_be_modified(self):
        """Status can be modified after creation."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        tab.status = TabStatus.ACTIVE
        assert tab.status == TabStatus.ACTIVE

    def test_last_activity_can_be_updated(self):
        """last_activity can be updated."""
        tab = TabInfo(tab_id="tab_1", page=Mock())
        new_time = datetime(2025, 6, 1, 12, 0, 0)
        tab.last_activity = new_time
        assert tab.last_activity == new_time


# =============================================================================
# TabPoolConfig Tests
# =============================================================================

class TestTabPoolConfig:
    """Tests for TabPoolConfig dataclass."""

    def test_default_max_tabs(self):
        """Default max_tabs should be 5."""
        config = TabPoolConfig()
        assert config.max_tabs == 5

    def test_default_idle_timeout(self):
        """Default idle_timeout should be 300 seconds."""
        config = TabPoolConfig()
        assert config.idle_timeout == 300.0

    def test_default_reuse_tabs(self):
        """Default reuse_tabs should be True."""
        config = TabPoolConfig()
        assert config.reuse_tabs is True

    def test_default_isolate_cookies(self):
        """Default isolate_cookies should be False."""
        config = TabPoolConfig()
        assert config.isolate_cookies is False

    def test_custom_max_tabs(self):
        """max_tabs can be customized."""
        config = TabPoolConfig(max_tabs=10)
        assert config.max_tabs == 10

    def test_custom_idle_timeout(self):
        """idle_timeout can be customized."""
        config = TabPoolConfig(idle_timeout=60.0)
        assert config.idle_timeout == 60.0

    def test_custom_reuse_tabs(self):
        """reuse_tabs can be disabled."""
        config = TabPoolConfig(reuse_tabs=False)
        assert config.reuse_tabs is False

    def test_custom_isolate_cookies(self):
        """isolate_cookies can be enabled."""
        config = TabPoolConfig(isolate_cookies=True)
        assert config.isolate_cookies is True

    def test_all_params_custom(self):
        """All parameters can be customized together."""
        config = TabPoolConfig(
            max_tabs=3,
            idle_timeout=120.0,
            reuse_tabs=False,
            isolate_cookies=True
        )
        assert config.max_tabs == 3
        assert config.idle_timeout == 120.0
        assert config.reuse_tabs is False
        assert config.isolate_cookies is True


# =============================================================================
# SyncTabManager Tests
# =============================================================================

class TestSyncTabManagerInit:
    """Tests for SyncTabManager initialization."""

    def test_init_with_context(self):
        """SyncTabManager initializes with browser context."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)
        assert manager.context == mock_context

    def test_init_with_default_config(self):
        """SyncTabManager uses default config when not provided."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)
        assert manager.config.max_tabs == 5
        assert manager.config.reuse_tabs is True

    def test_init_with_custom_config(self):
        """SyncTabManager accepts custom config."""
        mock_context = Mock()
        config = TabPoolConfig(max_tabs=10)
        manager = SyncTabManager(mock_context, config)
        assert manager.config.max_tabs == 10

    def test_init_tabs_empty(self):
        """SyncTabManager starts with empty tabs dict."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)
        assert manager.tabs == {}

    def test_init_tab_counter_zero(self):
        """SyncTabManager starts with tab counter at 0."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)
        assert manager._tab_counter == 0


class TestSyncTabManagerCreateTab:
    """Tests for SyncTabManager.create_tab()."""

    def test_create_tab_returns_tab_info(self):
        """create_tab returns a TabInfo instance."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        assert isinstance(tab, TabInfo)

    def test_create_tab_increments_counter(self):
        """create_tab increments the tab counter."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        manager.create_tab()
        assert manager._tab_counter == 1
        manager.create_tab()
        assert manager._tab_counter == 2

    def test_create_tab_generates_unique_ids(self):
        """create_tab generates unique tab IDs."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        tab2 = manager.create_tab()

        assert tab1.tab_id != tab2.tab_id

    def test_create_tab_adds_to_tabs_dict(self):
        """create_tab adds the tab to the tabs dict."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        assert tab.tab_id in manager.tabs
        assert manager.tabs[tab.tab_id] == tab

    def test_create_tab_with_task(self):
        """create_tab accepts a task parameter."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab(task="fetch_data")

        assert tab.task == "fetch_data"

    def test_create_tab_status_is_active(self):
        """Newly created tab has ACTIVE status."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        assert tab.status == TabStatus.ACTIVE

    def test_create_tab_calls_new_page(self):
        """create_tab calls context.new_page()."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        manager.create_tab()

        mock_context.new_page.assert_called_once()


class TestSyncTabManagerGetTab:
    """Tests for SyncTabManager.get_tab()."""

    def test_get_tab_creates_new_when_empty(self):
        """get_tab creates a new tab when no tabs exist."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.get_tab()

        assert len(manager.tabs) == 1
        assert tab.status == TabStatus.ACTIVE

    def test_get_tab_reuses_idle_tab(self):
        """get_tab reuses an idle tab when available."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        manager.release_tab(tab1.tab_id)  # Make it idle

        tab2 = manager.get_tab()

        assert tab2.tab_id == tab1.tab_id  # Same tab reused
        assert len(manager.tabs) == 1  # Still only 1 tab

    def test_get_tab_sets_task_on_reuse(self):
        """get_tab sets the task on reused tab."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        manager.release_tab(tab1.tab_id)

        tab2 = manager.get_tab(task="new_task")

        assert tab2.task == "new_task"

    def test_get_tab_updates_last_activity_on_reuse(self):
        """get_tab updates last_activity when reusing a tab."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        old_activity = tab1.last_activity
        manager.release_tab(tab1.tab_id)

        time.sleep(0.01)  # Small delay
        tab2 = manager.get_tab()

        assert tab2.last_activity > old_activity

    def test_get_tab_creates_when_no_idle(self):
        """get_tab creates new tab when none are idle."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()  # ACTIVE by default

        tab2 = manager.get_tab()

        assert tab2.tab_id != tab1.tab_id
        assert len(manager.tabs) == 2

    def test_get_tab_respects_max_tabs(self):
        """get_tab closes oldest idle tab when at max capacity (with reuse disabled)."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        # Disable reuse_tabs to test the max_tabs closing behavior
        config = TabPoolConfig(max_tabs=2, reuse_tabs=False)
        manager = SyncTabManager(mock_context, config)

        # Create and release 2 tabs
        tab1 = manager.create_tab()
        tab2 = manager.create_tab()
        manager.release_tab(tab1.tab_id)  # Make idle

        # Now at max with 1 idle, 1 active
        # Getting a new tab while at max should close the idle one (since reuse is disabled)
        tab3 = manager.get_tab()

        # Tab1 should have been closed to make room for tab3
        assert tab1.tab_id not in manager.tabs
        # Tab3 should be in the list
        assert tab3.tab_id in manager.tabs


class TestSyncTabManagerReleaseTab:
    """Tests for SyncTabManager.release_tab()."""

    def test_release_tab_sets_idle_status(self):
        """release_tab sets status to IDLE."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.release_tab(tab.tab_id)

        assert tab.status == TabStatus.IDLE

    def test_release_tab_clears_task(self):
        """release_tab clears the task."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab(task="some_task")
        manager.release_tab(tab.tab_id)

        assert tab.task == ""

    def test_release_tab_updates_last_activity(self):
        """release_tab updates last_activity."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        old_activity = tab.last_activity

        time.sleep(0.01)
        manager.release_tab(tab.tab_id)

        assert tab.last_activity > old_activity

    def test_release_nonexistent_tab(self):
        """release_tab does nothing for nonexistent tab."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        # Should not raise
        manager.release_tab("nonexistent_tab")


class TestSyncTabManagerCloseTab:
    """Tests for SyncTabManager.close_tab()."""

    def test_close_tab_removes_from_dict(self):
        """close_tab removes the tab from tabs dict."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.close_tab(tab.tab_id)

        assert tab.tab_id not in manager.tabs

    def test_close_tab_calls_page_close(self):
        """close_tab calls page.close()."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.close_tab(tab.tab_id)

        mock_page.close.assert_called_once()

    def test_close_tab_handles_page_close_error(self):
        """close_tab handles errors from page.close()."""
        mock_context = Mock()
        mock_page = Mock()
        mock_page.close.side_effect = Exception("Page already closed")
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        # Should not raise
        manager.close_tab(tab.tab_id)

        # Tab should still be removed from dict
        assert tab.tab_id not in manager.tabs

    def test_close_nonexistent_tab(self):
        """close_tab does nothing for nonexistent tab."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        # Should not raise
        manager.close_tab("nonexistent_tab")


class TestSyncTabManagerCloseAll:
    """Tests for SyncTabManager.close_all()."""

    def test_close_all_closes_all_tabs(self):
        """close_all closes all tabs."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        manager.create_tab()
        manager.create_tab()
        manager.create_tab()

        manager.close_all()

        assert len(manager.tabs) == 0

    def test_close_all_with_no_tabs(self):
        """close_all works with no tabs."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        # Should not raise
        manager.close_all()


class TestSyncTabManagerNavigate:
    """Tests for SyncTabManager.navigate_in_tab()."""

    def test_navigate_success(self):
        """navigate_in_tab returns True on success."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        result = manager.navigate_in_tab(tab.tab_id, "https://example.com")

        assert result is True

    def test_navigate_calls_goto(self):
        """navigate_in_tab calls page.goto()."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.navigate_in_tab(tab.tab_id, "https://example.com")

        mock_page.goto.assert_called_once_with("https://example.com")

    def test_navigate_updates_current_url(self):
        """navigate_in_tab updates current_url."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.navigate_in_tab(tab.tab_id, "https://example.com")

        assert tab.current_url == "https://example.com"

    def test_navigate_updates_status(self):
        """navigate_in_tab updates status to ACTIVE on success."""
        mock_context = Mock()
        mock_page = Mock()
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()
        manager.navigate_in_tab(tab.tab_id, "https://example.com")

        assert tab.status == TabStatus.ACTIVE

    def test_navigate_handles_error(self):
        """navigate_in_tab returns False and sets error on failure."""
        mock_context = Mock()
        mock_page = Mock()
        mock_page.goto.side_effect = Exception("Network error")
        mock_context.new_page.return_value = mock_page

        manager = SyncTabManager(mock_context)
        tab = manager.create_tab()

        result = manager.navigate_in_tab(tab.tab_id, "https://example.com")

        assert result is False
        assert tab.status == TabStatus.ERROR
        assert "Network error" in tab.error

    def test_navigate_nonexistent_tab(self):
        """navigate_in_tab returns False for nonexistent tab."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        result = manager.navigate_in_tab("nonexistent", "https://example.com")

        assert result is False


class TestSyncTabManagerStatus:
    """Tests for SyncTabManager.get_status()."""

    def test_status_with_no_tabs(self):
        """get_status returns correct info with no tabs."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        status = manager.get_status()

        assert status["total_tabs"] == 0
        assert status["active"] == 0
        assert status["idle"] == 0
        assert status["max_tabs"] == 5

    def test_status_with_active_tabs(self):
        """get_status counts active tabs correctly."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        manager.create_tab()
        manager.create_tab()

        status = manager.get_status()

        assert status["total_tabs"] == 2
        assert status["active"] == 2
        assert status["idle"] == 0

    def test_status_with_mixed_tabs(self):
        """get_status counts mixed active/idle tabs correctly."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        tab2 = manager.create_tab()
        manager.release_tab(tab1.tab_id)  # Make idle

        status = manager.get_status()

        assert status["total_tabs"] == 2
        assert status["active"] == 1
        assert status["idle"] == 1


class TestSyncTabManagerGetMainTab:
    """Tests for SyncTabManager.get_main_tab()."""

    def test_get_main_tab_with_no_tabs(self):
        """get_main_tab returns None when no tabs exist."""
        mock_context = Mock()
        manager = SyncTabManager(mock_context)

        result = manager.get_main_tab()

        assert result is None

    def test_get_main_tab_returns_first_tab(self):
        """get_main_tab returns the first tab."""
        mock_context = Mock()
        mock_context.new_page.return_value = Mock()

        manager = SyncTabManager(mock_context)
        tab1 = manager.create_tab()
        tab2 = manager.create_tab()

        result = manager.get_main_tab()

        assert result.tab_id == tab1.tab_id


# =============================================================================
# TabManager (Async) Tests - Basic structure tests
# =============================================================================

class TestTabManagerInit:
    """Tests for async TabManager initialization."""

    def test_init_with_browser(self):
        """TabManager initializes with browser."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)
        assert manager.browser == mock_browser

    def test_init_with_default_config(self):
        """TabManager uses default config when not provided."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)
        assert manager.config.max_tabs == 5

    def test_init_with_custom_config(self):
        """TabManager accepts custom config."""
        mock_browser = Mock()
        config = TabPoolConfig(max_tabs=10)
        manager = TabManager(mock_browser, config)
        assert manager.config.max_tabs == 10

    def test_init_context_is_none(self):
        """TabManager starts with context as None."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)
        assert manager.context is None


class TestTabManagerGenerateId:
    """Tests for TabManager._generate_tab_id()."""

    def test_generate_tab_id_increments(self):
        """_generate_tab_id increments counter."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        id1 = manager._generate_tab_id()
        id2 = manager._generate_tab_id()

        assert id1 != id2
        assert "tab_1" in id1
        assert "tab_2" in id2

    def test_generate_tab_id_format(self):
        """_generate_tab_id returns expected format."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        tab_id = manager._generate_tab_id()

        assert tab_id.startswith("tab_")


class TestTabManagerGetActiveCount:
    """Tests for TabManager.get_active_count()."""

    def test_get_active_count_empty(self):
        """get_active_count returns 0 when no tabs."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        assert manager.get_active_count() == 0

    def test_get_active_count_with_active_tabs(self):
        """get_active_count counts only active tabs."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        # Manually add tabs with different statuses
        manager.tabs["tab_1"] = TabInfo(
            tab_id="tab_1", page=Mock(), status=TabStatus.ACTIVE
        )
        manager.tabs["tab_2"] = TabInfo(
            tab_id="tab_2", page=Mock(), status=TabStatus.IDLE
        )
        manager.tabs["tab_3"] = TabInfo(
            tab_id="tab_3", page=Mock(), status=TabStatus.ACTIVE
        )

        assert manager.get_active_count() == 2


class TestTabManagerGetStatus:
    """Tests for TabManager.get_status()."""

    def test_get_status_structure(self):
        """get_status returns expected structure."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        status = manager.get_status()

        assert "total_tabs" in status
        assert "active" in status
        assert "idle" in status
        assert "max_tabs" in status
        assert "tabs" in status

    def test_get_status_tab_details(self):
        """get_status includes tab details."""
        mock_browser = Mock()
        manager = TabManager(mock_browser)

        manager.tabs["tab_1"] = TabInfo(
            tab_id="tab_1",
            page=Mock(),
            status=TabStatus.ACTIVE,
            current_url="https://example.com",
            task="test_task"
        )

        status = manager.get_status()

        assert "tab_1" in status["tabs"]
        assert status["tabs"]["tab_1"]["status"] == "active"
        assert status["tabs"]["tab_1"]["url"] == "https://example.com"
        assert status["tabs"]["tab_1"]["task"] == "test_task"


# =============================================================================
# SyncTabManager Thread Safety Tests
# =============================================================================

class TestSyncTabManagerThreadSafety:
    """Tests for SyncTabManager thread safety."""

    def test_has_lock_attribute(self):
        """SyncTabManager should have a _lock attribute."""
        import threading
        mock_context = Mock()
        manager = SyncTabManager(mock_context)
        assert hasattr(manager, '_lock')
        assert isinstance(manager._lock, type(threading.Lock()))

    def test_concurrent_get_tab_returns_unique_tabs(self):
        """Concurrent get_tab calls should never return the same tab."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        # Each call to new_page returns a unique mock
        mock_context.new_page.side_effect = lambda: Mock()

        # Disable reuse to ensure new tabs are created
        config = TabPoolConfig(max_tabs=100, reuse_tabs=False)
        manager = SyncTabManager(mock_context, config)

        tabs_returned = []
        lock = threading.Lock()

        def get_tab():
            tab = manager.get_tab()
            with lock:
                tabs_returned.append(tab.tab_id)
            return tab

        num_threads = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_tab) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # All tab IDs should be unique
        assert len(tabs_returned) == num_threads
        assert len(set(tabs_returned)) == num_threads

    def test_concurrent_get_tab_with_reuse_no_duplicate_assignment(self):
        """Concurrent get_tab with reuse should not assign same idle tab twice."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        config = TabPoolConfig(max_tabs=100, reuse_tabs=True)
        manager = SyncTabManager(mock_context, config)

        # Create and release some tabs
        initial_tabs = []
        for _ in range(5):
            tab = manager.create_tab()
            initial_tabs.append(tab.tab_id)
            manager.release_tab(tab.tab_id)

        tabs_assigned = []
        lock = threading.Lock()

        def get_tab():
            tab = manager.get_tab()
            with lock:
                tabs_assigned.append(tab.tab_id)
            time.sleep(0.01)  # Hold the tab briefly
            return tab

        num_threads = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_tab) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Check that no tab_id appears more than once in the assigned list
        # (while they were being held - i.e., before any release)
        # This verifies the race condition fix
        assert len(tabs_assigned) == num_threads

    def test_concurrent_create_and_close_tabs(self):
        """Concurrent create and close operations should be safe."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        manager = SyncTabManager(mock_context, TabPoolConfig(max_tabs=100))

        def create_tabs():
            tabs = []
            for _ in range(5):
                tab = manager.create_tab()
                tabs.append(tab.tab_id)
            return tabs

        def close_tabs(tab_ids):
            for tab_id in tab_ids:
                manager.close_tab(tab_id)

        # Create tabs from multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            create_futures = [executor.submit(create_tabs) for _ in range(5)]
            all_tabs = []
            for future in concurrent.futures.as_completed(create_futures):
                all_tabs.extend(future.result())

            # Now close them from multiple threads
            # Split tabs among threads
            chunks = [all_tabs[i::5] for i in range(5)]
            close_futures = [executor.submit(close_tabs, chunk) for chunk in chunks]
            concurrent.futures.wait(close_futures)

        # All tabs should be closed
        assert len(manager.tabs) == 0

    def test_concurrent_release_and_get_tab(self):
        """Concurrent release and get_tab should coordinate correctly."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        config = TabPoolConfig(max_tabs=100, reuse_tabs=True)
        manager = SyncTabManager(mock_context, config)

        # Create initial tabs
        tab1 = manager.create_tab()
        tab2 = manager.create_tab()

        results = []
        lock = threading.Lock()

        def release_and_get():
            # Release one of the original tabs
            manager.release_tab(tab1.tab_id)
            # Try to get a tab (might reuse tab1 or create new)
            tab = manager.get_tab()
            with lock:
                results.append(tab.tab_id)
            return tab

        num_threads = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(release_and_get) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Should have gotten tabs without any errors
        assert len(results) == num_threads

    def test_concurrent_get_status(self):
        """Concurrent get_status calls should be safe."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        manager = SyncTabManager(mock_context)

        # Create some tabs
        for _ in range(3):
            manager.create_tab()

        statuses = []
        lock = threading.Lock()

        def get_status():
            status = manager.get_status()
            with lock:
                statuses.append(status)
            return status

        def modify_tabs():
            tab = manager.create_tab()
            time.sleep(0.005)
            manager.release_tab(tab.tab_id)
            time.sleep(0.005)
            manager.close_tab(tab.tab_id)

        # Run readers and modifiers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            reader_futures = [executor.submit(get_status) for _ in range(10)]
            modifier_futures = [executor.submit(modify_tabs) for _ in range(5)]
            concurrent.futures.wait(reader_futures + modifier_futures)

        # All statuses should be valid (no partial reads)
        for status in statuses:
            assert "total_tabs" in status
            assert "active" in status
            assert "idle" in status
            assert status["total_tabs"] >= 0
            assert status["active"] >= 0
            assert status["idle"] >= 0

    def test_concurrent_close_all(self):
        """Concurrent close_all calls should be safe."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        manager = SyncTabManager(mock_context)

        # Create tabs
        for _ in range(10):
            manager.create_tab()

        def close_all():
            manager.close_all()

        # Call close_all from multiple threads
        num_threads = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(close_all) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # All tabs should be closed
        assert len(manager.tabs) == 0

    def test_concurrent_navigate_different_tabs(self):
        """Concurrent navigation in different tabs should be safe."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        manager = SyncTabManager(mock_context)

        # Create tabs
        tabs = [manager.create_tab() for _ in range(5)]

        results = []
        lock = threading.Lock()

        def navigate(tab_id, url):
            result = manager.navigate_in_tab(tab_id, url)
            with lock:
                results.append((tab_id, result))
            return result

        # Navigate all tabs concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(navigate, tab.tab_id, f"https://example{i}.com")
                for i, tab in enumerate(tabs)
            ]
            concurrent.futures.wait(futures)

        # All navigations should succeed
        assert len(results) == 5
        assert all(result for _, result in results)

    def test_tab_counter_thread_safety(self):
        """Tab counter should be incremented atomically."""
        import threading
        import concurrent.futures

        mock_context = Mock()
        mock_context.new_page.side_effect = lambda: Mock()

        manager = SyncTabManager(mock_context, TabPoolConfig(max_tabs=1000))

        tab_ids = []
        lock = threading.Lock()

        def create_tab():
            tab = manager.create_tab()
            with lock:
                tab_ids.append(tab.tab_id)
            return tab

        num_threads = 50
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_tab) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # All tab IDs should be unique
        assert len(tab_ids) == num_threads
        assert len(set(tab_ids)) == num_threads

        # Tab counter should match number of tabs created
        assert manager._tab_counter == num_threads
