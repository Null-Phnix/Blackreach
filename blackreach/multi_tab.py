"""
Multi-Tab Browser Support (v3.0.0)

Provides multi-tab browser management:
- Tab pool for parallel operations
- Tab isolation for different tasks
- Tab lifecycle management
- Cross-tab coordination
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import asyncio
import threading


class TabStatus(Enum):
    """Status of a browser tab."""
    IDLE = "idle"
    LOADING = "loading"
    ACTIVE = "active"
    WAITING = "waiting"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class TabInfo:
    """Information about a browser tab."""
    tab_id: str
    page: Any  # Playwright Page object
    status: TabStatus = TabStatus.IDLE
    current_url: str = ""
    task: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class TabPoolConfig:
    """Configuration for the tab pool."""
    max_tabs: int = 5
    idle_timeout: float = 300.0  # Close idle tabs after 5 minutes
    reuse_tabs: bool = True
    isolate_cookies: bool = False  # Use separate contexts if True


class TabManager:
    """Manages multiple browser tabs."""

    def __init__(self, browser, config: Optional[TabPoolConfig] = None):
        self.browser = browser
        self.config = config or TabPoolConfig()
        self.tabs: Dict[str, TabInfo] = {}
        self.context = None  # Browser context
        self._tab_counter = 0
        self._lock = asyncio.Lock() if asyncio else None

    async def initialize(self):
        """Initialize the tab manager with a browser context."""
        if not self.context:
            self.context = await self.browser.new_context()

    def _generate_tab_id(self) -> str:
        """Generate a unique tab ID."""
        self._tab_counter += 1
        return f"tab_{self._tab_counter}"

    async def get_tab(self, task: str = "") -> TabInfo:
        """Get an available tab or create a new one."""
        # Look for an idle tab to reuse
        if self.config.reuse_tabs:
            for tab in self.tabs.values():
                if tab.status == TabStatus.IDLE:
                    tab.status = TabStatus.ACTIVE
                    tab.task = task
                    tab.last_activity = datetime.now()
                    return tab

        # Check if we can create a new tab
        if len(self.tabs) >= self.config.max_tabs:
            # Close oldest idle tab
            await self._close_oldest_idle()

        # Create new tab
        return await self.create_tab(task)

    async def create_tab(self, task: str = "") -> TabInfo:
        """Create a new browser tab."""
        if not self.context:
            await self.initialize()

        page = await self.context.new_page()
        tab_id = self._generate_tab_id()

        tab = TabInfo(
            tab_id=tab_id,
            page=page,
            status=TabStatus.ACTIVE,
            task=task
        )

        self.tabs[tab_id] = tab
        return tab

    async def release_tab(self, tab_id: str):
        """Release a tab back to the pool."""
        if tab_id in self.tabs:
            tab = self.tabs[tab_id]
            tab.status = TabStatus.IDLE
            tab.task = ""
            tab.last_activity = datetime.now()

    async def close_tab(self, tab_id: str):
        """Close a specific tab."""
        if tab_id in self.tabs:
            tab = self.tabs[tab_id]
            try:
                await tab.page.close()
            except Exception:
                pass  # Best-effort cleanup
            tab.status = TabStatus.CLOSED
            del self.tabs[tab_id]

    async def close_all(self):
        """Close all tabs."""
        for tab_id in list(self.tabs.keys()):
            await self.close_tab(tab_id)

        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass  # Best-effort cleanup
            self.context = None

    async def _close_oldest_idle(self):
        """Close the oldest idle tab."""
        idle_tabs = [
            t for t in self.tabs.values()
            if t.status == TabStatus.IDLE
        ]

        if idle_tabs:
            oldest = min(idle_tabs, key=lambda t: t.last_activity)
            await self.close_tab(oldest.tab_id)

    async def cleanup_stale(self):
        """Close tabs that have been idle too long."""
        now = datetime.now()
        for tab in list(self.tabs.values()):
            if tab.status == TabStatus.IDLE:
                idle_time = (now - tab.last_activity).total_seconds()
                if idle_time > self.config.idle_timeout:
                    await self.close_tab(tab.tab_id)

    def get_active_count(self) -> int:
        """Get count of active tabs."""
        return sum(1 for t in self.tabs.values() if t.status == TabStatus.ACTIVE)

    def get_status(self) -> Dict:
        """Get overall tab pool status."""
        return {
            "total_tabs": len(self.tabs),
            "active": sum(1 for t in self.tabs.values() if t.status == TabStatus.ACTIVE),
            "idle": sum(1 for t in self.tabs.values() if t.status == TabStatus.IDLE),
            "max_tabs": self.config.max_tabs,
            "tabs": {
                tab_id: {
                    "status": tab.status.value,
                    "url": tab.current_url,
                    "task": tab.task
                }
                for tab_id, tab in self.tabs.items()
            }
        }


class SyncTabManager:
    """Synchronous wrapper for TabManager for non-async code (thread-safe)."""

    def __init__(self, browser_context, config: Optional[TabPoolConfig] = None):
        self.context = browser_context
        self.config = config or TabPoolConfig()
        self.tabs: Dict[str, TabInfo] = {}
        self._tab_counter = 0
        self._lock = threading.Lock()

    def _generate_tab_id(self) -> str:
        """Generate a unique tab ID (assumes caller holds lock)."""
        self._tab_counter += 1
        return f"tab_{self._tab_counter}"

    def get_tab(self, task: str = "") -> TabInfo:
        """Get an available tab or create a new one (thread-safe)."""
        with self._lock:
            # Look for an idle tab to reuse
            if self.config.reuse_tabs:
                for tab in self.tabs.values():
                    if tab.status == TabStatus.IDLE:
                        tab.status = TabStatus.ACTIVE
                        tab.task = task
                        tab.last_activity = datetime.now()
                        return tab

            # Check if we can create a new tab
            if len(self.tabs) >= self.config.max_tabs:
                self._close_oldest_idle_unlocked()

            return self._create_tab_unlocked(task)

    def _create_tab_unlocked(self, task: str = "") -> TabInfo:
        """Create a new browser tab (assumes caller holds lock)."""
        page = self.context.new_page()
        tab_id = self._generate_tab_id()

        tab = TabInfo(
            tab_id=tab_id,
            page=page,
            status=TabStatus.ACTIVE,
            task=task
        )

        self.tabs[tab_id] = tab
        return tab

    def create_tab(self, task: str = "") -> TabInfo:
        """Create a new browser tab (thread-safe)."""
        with self._lock:
            return self._create_tab_unlocked(task)

    def release_tab(self, tab_id: str):
        """Release a tab back to the pool (thread-safe)."""
        with self._lock:
            if tab_id in self.tabs:
                tab = self.tabs[tab_id]
                tab.status = TabStatus.IDLE
                tab.task = ""
                tab.last_activity = datetime.now()

    def _close_tab_unlocked(self, tab_id: str):
        """Close a specific tab (assumes caller holds lock)."""
        if tab_id in self.tabs:
            tab = self.tabs[tab_id]
            try:
                tab.page.close()
            except Exception:
                pass  # Best-effort cleanup
            tab.status = TabStatus.CLOSED
            del self.tabs[tab_id]

    def close_tab(self, tab_id: str):
        """Close a specific tab (thread-safe)."""
        with self._lock:
            self._close_tab_unlocked(tab_id)

    def close_all(self):
        """Close all tabs (thread-safe)."""
        with self._lock:
            for tab_id in list(self.tabs.keys()):
                self._close_tab_unlocked(tab_id)

    def _close_oldest_idle_unlocked(self):
        """Close the oldest idle tab (assumes caller holds lock).

        Skips tabs with LOADING status to avoid closing tabs mid-navigation.
        """
        idle_tabs = [
            t for t in self.tabs.values()
            if t.status == TabStatus.IDLE
        ]

        if idle_tabs:
            oldest = min(idle_tabs, key=lambda t: t.last_activity)
            self._close_tab_unlocked(oldest.tab_id)

    def _close_oldest_idle(self):
        """Close the oldest idle tab (thread-safe)."""
        with self._lock:
            self._close_oldest_idle_unlocked()

    def get_main_tab(self) -> Optional[TabInfo]:
        """Get the main/first tab (thread-safe)."""
        with self._lock:
            if self.tabs:
                return next(iter(self.tabs.values()))
            return None

    def navigate_in_tab(self, tab_id: str, url: str) -> bool:
        """Navigate a specific tab to a URL (thread-safe)."""
        with self._lock:
            if tab_id not in self.tabs:
                return False
            tab = self.tabs[tab_id]
            tab.status = TabStatus.LOADING
            page = tab.page  # Capture stable reference under lock

        try:
            page.goto(url)
            with self._lock:
                if tab_id in self.tabs:
                    tab.current_url = url
                    tab.status = TabStatus.ACTIVE
                    tab.last_activity = datetime.now()
            return True
        except Exception as e:
            with self._lock:
                if tab_id in self.tabs:
                    tab.status = TabStatus.ERROR
                    tab.error = str(e)
            return False

    def get_status(self) -> Dict:
        """Get overall tab pool status (thread-safe)."""
        with self._lock:
            return {
                "total_tabs": len(self.tabs),
                "active": sum(1 for t in self.tabs.values() if t.status == TabStatus.ACTIVE),
                "idle": sum(1 for t in self.tabs.values() if t.status == TabStatus.IDLE),
                "max_tabs": self.config.max_tabs,
            }
