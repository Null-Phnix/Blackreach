"""
Unit tests for blackreach/task_scheduler.py

Tests task scheduling with priorities, dependencies, and parallel execution.
"""

import pytest
import time
from datetime import datetime
from blackreach.task_scheduler import (
    TaskPriority,
    TaskStatus,
    Task,
    TaskGroup,
    TaskScheduler,
    get_scheduler,
)


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_all_priorities_exist(self):
        """All expected task priorities should exist."""
        assert TaskPriority.CRITICAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.NORMAL.value == 3
        assert TaskPriority.LOW.value == 4
        assert TaskPriority.IDLE.value == 5

    def test_priority_ordering(self):
        """CRITICAL should have lowest numeric value (highest priority)."""
        assert TaskPriority.CRITICAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.LOW.value
        assert TaskPriority.LOW.value < TaskPriority.IDLE.value


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_statuses_exist(self):
        """All expected task statuses should exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.READY.value == "ready"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.BLOCKED.value == "blocked"


class TestTask:
    """Tests for Task dataclass."""

    def test_default_values(self):
        """Task has correct defaults."""
        task = Task(
            task_id="test_1",
            name="Test Task",
            action="navigate"
        )
        assert task.task_id == "test_1"
        assert task.name == "Test Task"
        assert task.action == "navigate"
        assert task.params == {}
        assert task.priority == TaskPriority.NORMAL
        assert task.status == TaskStatus.PENDING
        assert task.dependencies == []
        assert task.result is None
        assert task.error is None
        assert task.retries == 0
        assert task.max_retries == 2

    def test_custom_values(self):
        """Task accepts custom values."""
        task = Task(
            task_id="task_2",
            name="High Priority Task",
            action="download",
            params={"url": "http://example.com"},
            priority=TaskPriority.HIGH,
            dependencies=["task_1"],
            max_retries=5
        )
        assert task.priority == TaskPriority.HIGH
        assert task.params == {"url": "http://example.com"}
        assert task.dependencies == ["task_1"]
        assert task.max_retries == 5

    def test_task_comparison_by_priority(self):
        """Tasks should compare by priority for queue ordering."""
        high_task = Task(task_id="1", name="High", action="test", priority=TaskPriority.HIGH)
        low_task = Task(task_id="2", name="Low", action="test", priority=TaskPriority.LOW)

        # Higher priority (lower value) should be "less than"
        assert high_task < low_task

    def test_task_comparison_by_creation_time(self):
        """Tasks with same priority should compare by creation time."""
        task1 = Task(task_id="1", name="First", action="test")
        time.sleep(0.01)  # Small delay to ensure different timestamps
        task2 = Task(task_id="2", name="Second", action="test")

        # Earlier task should be "less than"
        assert task1 < task2


class TestTaskGroup:
    """Tests for TaskGroup dataclass."""

    def test_default_values(self):
        """TaskGroup has correct defaults."""
        group = TaskGroup(
            group_id="group_1",
            name="Test Group"
        )
        assert group.group_id == "group_1"
        assert group.name == "Test Group"
        assert group.tasks == []
        assert group.parallel is False

    def test_parallel_group(self):
        """TaskGroup can be configured for parallel execution."""
        group = TaskGroup(
            group_id="parallel_group",
            name="Parallel Tasks",
            parallel=True
        )
        assert group.parallel is True


class TestTaskScheduler:
    """Tests for TaskScheduler class."""

    def test_init(self):
        """TaskScheduler initializes correctly."""
        scheduler = TaskScheduler()
        assert scheduler is not None
        assert scheduler.max_parallel == 3

    def test_init_with_max_parallel(self):
        """TaskScheduler accepts custom max_parallel."""
        scheduler = TaskScheduler(max_parallel=5)
        assert scheduler.max_parallel == 5

    def test_add_task(self):
        """Should add a task to the scheduler."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(
            name="Test Task",
            action="navigate",
            params={"url": "http://example.com"}
        )

        assert task_id is not None
        assert task_id.startswith("task_")

        task = scheduler.get_task(task_id)
        assert task is not None
        assert task.name == "Test Task"
        assert task.action == "navigate"

    def test_add_task_with_priority(self):
        """Should add a task with custom priority."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(
            name="Critical Task",
            action="download",
            priority=TaskPriority.CRITICAL
        )

        task = scheduler.get_task(task_id)
        assert task.priority == TaskPriority.CRITICAL

    def test_task_ready_when_no_dependencies(self):
        """Task without dependencies should be READY."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(
            name="Independent Task",
            action="navigate"
        )

        task = scheduler.get_task(task_id)
        assert task.status == TaskStatus.READY

    def test_task_blocked_with_pending_dependencies(self):
        """Task with unmet dependencies should be BLOCKED."""
        scheduler = TaskScheduler()
        task1_id = scheduler.add_task(name="First", action="navigate")
        task2_id = scheduler.add_task(
            name="Second",
            action="click",
            dependencies=[task1_id]
        )

        task2 = scheduler.get_task(task2_id)
        assert task2.status == TaskStatus.BLOCKED


class TestTaskSchedulerExecution:
    """Tests for task execution flow."""

    def test_get_next_task(self):
        """Should return the next ready task."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(name="Task 1", action="navigate")

        next_task = scheduler.get_next()
        assert next_task is not None
        assert next_task.task_id == task_id
        assert next_task.status == TaskStatus.RUNNING

    def test_get_next_respects_priority(self):
        """Should return highest priority task first."""
        scheduler = TaskScheduler()
        low_id = scheduler.add_task(name="Low", action="test", priority=TaskPriority.LOW)
        high_id = scheduler.add_task(name="High", action="test", priority=TaskPriority.HIGH)

        next_task = scheduler.get_next()
        assert next_task.task_id == high_id

    def test_get_next_respects_max_parallel(self):
        """Should not return task when max_parallel reached."""
        scheduler = TaskScheduler(max_parallel=1)
        scheduler.add_task(name="Task 1", action="navigate")
        scheduler.add_task(name="Task 2", action="click")

        # Get first task
        task1 = scheduler.get_next()
        assert task1 is not None

        # Should not get another while one is running
        task2 = scheduler.get_next()
        assert task2 is None

    def test_complete_task(self):
        """Should mark task as completed."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(name="Task", action="navigate")

        scheduler.get_next()  # Start the task
        scheduler.complete_task(task_id, result="success")

        task = scheduler.get_task(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "success"
        assert task.completed_at is not None

    def test_complete_unblocks_dependents(self):
        """Completing a task should unblock dependent tasks."""
        scheduler = TaskScheduler()
        task1_id = scheduler.add_task(name="First", action="navigate")
        task2_id = scheduler.add_task(
            name="Second",
            action="click",
            dependencies=[task1_id]
        )

        # Task2 should be blocked
        task2 = scheduler.get_task(task2_id)
        assert task2.status == TaskStatus.BLOCKED

        # Complete task1
        scheduler.get_next()
        scheduler.complete_task(task1_id)

        # Task2 should now be ready
        task2 = scheduler.get_task(task2_id)
        assert task2.status == TaskStatus.READY

    def test_fail_task(self):
        """Should mark task as failed after max retries."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(name="Task", action="navigate")

        task = scheduler.get_task(task_id)
        task.max_retries = 2  # Allow 2 retries

        scheduler.get_next()
        scheduler.fail_task(task_id, "Error 1")

        # Should be queued for retry (retries=1 < max_retries=2)
        task = scheduler.get_task(task_id)
        assert task.status == TaskStatus.READY
        assert task.retries == 1

        # Fail again - should now be FAILED (retries=2 >= max_retries=2)
        scheduler.get_next()
        scheduler.fail_task(task_id, "Error 2")

        task = scheduler.get_task(task_id)
        assert task.status == TaskStatus.FAILED

    def test_cancel_task(self):
        """Should cancel a task."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(name="Task", action="navigate")

        scheduler.cancel_task(task_id)

        task = scheduler.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED


class TestTaskSchedulerGroups:
    """Tests for task group functionality."""

    def test_create_group(self):
        """Should create a task group."""
        scheduler = TaskScheduler()
        group_id = scheduler.create_group(name="Test Group")

        assert group_id is not None
        assert group_id.startswith("group_")
        assert group_id in scheduler.groups

    def test_create_parallel_group(self):
        """Should create a parallel task group."""
        scheduler = TaskScheduler()
        group_id = scheduler.create_group(name="Parallel Group", parallel=True)

        group = scheduler.groups[group_id]
        assert group.parallel is True

    def test_add_to_group(self):
        """Should add task to group."""
        scheduler = TaskScheduler()
        group_id = scheduler.create_group(name="Group")
        task_id = scheduler.add_task(name="Task", action="test")

        scheduler.add_to_group(group_id, task_id)

        group = scheduler.groups[group_id]
        assert task_id in group.tasks


class TestTaskSchedulerStats:
    """Tests for scheduler statistics."""

    def test_get_stats(self):
        """Should return scheduler statistics."""
        scheduler = TaskScheduler()
        scheduler.add_task(name="Task 1", action="navigate")
        scheduler.add_task(name="Task 2", action="click")

        stats = scheduler.get_stats()

        assert stats["total_tasks"] == 2
        assert stats["running"] == 0
        assert stats["completed"] == 0
        assert "status_counts" in stats

    def test_get_pending_tasks(self):
        """Should return pending tasks."""
        scheduler = TaskScheduler()
        scheduler.add_task(name="Task 1", action="navigate")
        scheduler.add_task(name="Task 2", action="click")

        pending = scheduler.get_pending()
        assert len(pending) == 2

    def test_get_running_tasks(self):
        """Should return running tasks."""
        scheduler = TaskScheduler()
        scheduler.add_task(name="Task 1", action="navigate")

        scheduler.get_next()

        running = scheduler.get_running()
        assert len(running) == 1

    def test_has_pending(self):
        """Should check if there are pending tasks."""
        scheduler = TaskScheduler()

        assert scheduler.has_pending() is False

        scheduler.add_task(name="Task", action="navigate")
        assert scheduler.has_pending() is True


class TestTaskSchedulerCleanup:
    """Tests for cleanup functionality."""

    def test_clear_completed(self):
        """Should clear completed tasks."""
        scheduler = TaskScheduler()
        task_id = scheduler.add_task(name="Task", action="navigate")

        scheduler.get_next()
        scheduler.complete_task(task_id)

        assert task_id in scheduler.tasks

        scheduler.clear_completed()

        assert task_id not in scheduler.tasks


class TestTaskSchedulerCallbacks:
    """Tests for callback functionality."""

    def test_on_task_complete_callback(self):
        """Should call on_task_complete callback."""
        completed_tasks = []

        def on_complete(task):
            completed_tasks.append(task.task_id)

        scheduler = TaskScheduler(on_task_complete=on_complete)
        task_id = scheduler.add_task(name="Task", action="navigate")

        scheduler.get_next()
        scheduler.complete_task(task_id)

        assert task_id in completed_tasks

    def test_on_task_fail_callback(self):
        """Should call on_task_fail callback."""
        failed_tasks = []

        def on_fail(task, error):
            failed_tasks.append((task.task_id, error))

        scheduler = TaskScheduler(on_task_fail=on_fail)
        task_id = scheduler.add_task(name="Task", action="navigate")

        task = scheduler.get_task(task_id)
        task.max_retries = 0  # Fail immediately

        scheduler.get_next()
        scheduler.fail_task(task_id, "Test error")

        assert len(failed_tasks) == 1
        assert failed_tasks[0][1] == "Test error"


class TestGlobalScheduler:
    """Tests for global scheduler instance."""

    def test_get_scheduler(self):
        """Should return global scheduler instance."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        # Should return same instance
        assert scheduler1 is scheduler2

    def test_get_scheduler_with_max_parallel(self):
        """Should accept max_parallel on first call."""
        # Note: This test may be affected by previous tests
        scheduler = get_scheduler(max_parallel=10)
        assert scheduler is not None
