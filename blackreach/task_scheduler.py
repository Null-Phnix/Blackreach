"""
Task Scheduler System (v3.2.0)

Provides task scheduling for the agent:
- Sequential and parallel task execution
- Task dependencies
- Priority scheduling
- Task queue management
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
from enum import Enum
from queue import PriorityQueue
import threading
import time


class TaskPriority(Enum):
    """Priority levels for tasks."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    IDLE = 5


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    READY = "ready"         # Dependencies met
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"     # Waiting for dependencies


@dataclass
class Task:
    """Represents a schedulable task."""
    task_id: str
    name: str
    action: str             # Action type (navigate, download, search, etc.)
    params: Dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # Task IDs
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2

    def __lt__(self, other):
        """For priority queue comparison."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


@dataclass
class TaskGroup:
    """A group of related tasks."""
    group_id: str
    name: str
    tasks: List[str] = field(default_factory=list)  # Task IDs
    parallel: bool = False  # Execute tasks in parallel if True
    created_at: datetime = field(default_factory=datetime.now)


class TaskScheduler:
    """Schedules and manages task execution."""

    def __init__(
        self,
        max_parallel: int = 3,
        on_task_complete: Optional[Callable[[Task], None]] = None,
        on_task_fail: Optional[Callable[[Task, str], None]] = None
    ):
        self.max_parallel = max_parallel
        self.on_task_complete = on_task_complete
        self.on_task_fail = on_task_fail

        # Task tracking
        self.tasks: Dict[str, Task] = {}
        self.groups: Dict[str, TaskGroup] = {}
        self.queue: PriorityQueue = PriorityQueue()
        self.running: Set[str] = set()
        self.completed: Set[str] = set()

        # Threading
        self._lock = threading.Lock()
        self._counter = 0

    def _generate_id(self, prefix: str = "task") -> str:
        """Generate a unique ID."""
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def add_task(
        self,
        name: str,
        action: str,
        params: Dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: List[str] = None
    ) -> str:
        """Add a task to the scheduler."""
        task_id = self._generate_id("task")

        task = Task(
            task_id=task_id,
            name=name,
            action=action,
            params=params or {},
            priority=priority,
            dependencies=dependencies or []
        )

        with self._lock:
            self.tasks[task_id] = task

            # Check if ready to run
            if self._dependencies_met(task):
                task.status = TaskStatus.READY
                self.queue.put(task)
            else:
                task.status = TaskStatus.BLOCKED

        return task_id

    def create_group(
        self,
        name: str,
        parallel: bool = False
    ) -> str:
        """Create a task group."""
        group_id = self._generate_id("group")

        group = TaskGroup(
            group_id=group_id,
            name=name,
            parallel=parallel
        )

        self.groups[group_id] = group
        return group_id

    def add_to_group(self, group_id: str, task_id: str):
        """Add a task to a group."""
        if group_id in self.groups and task_id in self.tasks:
            self.groups[group_id].tasks.append(task_id)

    def _dependencies_met(self, task: Task) -> bool:
        """Check if all dependencies are completed."""
        return all(
            dep_id in self.completed
            for dep_id in task.dependencies
        )

    def get_next(self) -> Optional[Task]:
        """Get the next task to execute."""
        with self._lock:
            if len(self.running) >= self.max_parallel:
                return None

            try:
                while not self.queue.empty():
                    task = self.queue.get_nowait()

                    # Verify still ready (dependencies might have changed)
                    if task.status == TaskStatus.READY:
                        task.status = TaskStatus.RUNNING
                        task.started_at = datetime.now()
                        self.running.add(task.task_id)
                        return task
            except Exception:
                pass

        return None

    def complete_task(self, task_id: str, result: Any = None):
        """Mark a task as completed."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result

                self.running.discard(task_id)
                self.completed.add(task_id)

                # Update dependent tasks
                self._update_dependents(task_id)

                if self.on_task_complete:
                    self.on_task_complete(task)

    def fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.error = error
                task.retries += 1

                self.running.discard(task_id)

                # Retry if under limit
                if task.retries < task.max_retries:
                    task.status = TaskStatus.READY
                    self.queue.put(task)
                else:
                    task.status = TaskStatus.FAILED
                    if self.on_task_fail:
                        self.on_task_fail(task, error)

    def cancel_task(self, task_id: str):
        """Cancel a task."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = TaskStatus.CANCELLED
                self.running.discard(task_id)

    def _update_dependents(self, completed_id: str):
        """Update tasks that depend on the completed task."""
        for task in self.tasks.values():
            if task.status == TaskStatus.BLOCKED:
                if completed_id in task.dependencies:
                    if self._dependencies_met(task):
                        task.status = TaskStatus.READY
                        self.queue.put(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def get_pending(self) -> List[Task]:
        """Get all pending/ready tasks."""
        return [
            t for t in self.tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.BLOCKED)
        ]

    def get_running(self) -> List[Task]:
        """Get all running tasks."""
        return [
            self.tasks[tid] for tid in self.running
            if tid in self.tasks
        ]

    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        status_counts = {}
        for task in self.tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_tasks": len(self.tasks),
            "running": len(self.running),
            "completed": len(self.completed),
            "status_counts": status_counts,
            "groups": len(self.groups)
        }

    def has_pending(self) -> bool:
        """Check if there are pending tasks."""
        return any(
            t.status in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.RUNNING)
            for t in self.tasks.values()
        )

    def clear_completed(self):
        """Clear completed tasks."""
        with self._lock:
            to_remove = [
                tid for tid, task in self.tasks.items()
                if task.status == TaskStatus.COMPLETED
            ]
            for tid in to_remove:
                del self.tasks[tid]
                self.completed.discard(tid)

    def wait_all(self, timeout: float = None) -> bool:
        """Wait for all tasks to complete."""
        start = time.time()

        while self.has_pending():
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(0.5)

        return True


# Global task scheduler
_scheduler: Optional[TaskScheduler] = None


def get_scheduler(max_parallel: int = 3) -> TaskScheduler:
    """Get the global task scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler(max_parallel=max_parallel)
    return _scheduler
