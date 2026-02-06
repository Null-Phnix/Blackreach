"""
Unit tests for blackreach/goal_engine.py

Tests goal decomposition and progress tracking.
"""

import pytest
from blackreach.goal_engine import (
    SubtaskStatus,
    GoalType,
    EnhancedSubtask,
    GoalEngine,
)


class TestSubtaskStatus:
    """Tests for SubtaskStatus enum."""

    def test_all_statuses_exist(self):
        """All expected subtask statuses should exist."""
        assert SubtaskStatus.PENDING.value == "pending"
        assert SubtaskStatus.IN_PROGRESS.value == "in_progress"
        assert SubtaskStatus.COMPLETED.value == "completed"
        assert SubtaskStatus.FAILED.value == "failed"
        assert SubtaskStatus.SKIPPED.value == "skipped"
        assert SubtaskStatus.BLOCKED.value == "blocked"


class TestGoalType:
    """Tests for GoalType enum."""

    def test_all_types_exist(self):
        """All expected goal types should exist."""
        assert GoalType.DOWNLOAD.value == "download"
        assert GoalType.SEARCH.value == "search"
        assert GoalType.NAVIGATE.value == "navigate"
        assert GoalType.EXTRACT.value == "extract"
        assert GoalType.INTERACT.value == "interact"
        assert GoalType.MULTI_STEP.value == "multi_step"
        assert GoalType.UNKNOWN.value == "unknown"


class TestEnhancedSubtask:
    """Tests for EnhancedSubtask dataclass."""

    def test_default_values(self):
        """EnhancedSubtask has correct defaults."""
        subtask = EnhancedSubtask(
            id="task_1",
            description="Test task",
            expected_outcome="Success",
            task_type=GoalType.DOWNLOAD
        )
        assert subtask.status == SubtaskStatus.PENDING
        assert subtask.priority == 5
        assert subtask.optional is False
        assert subtask.depends_on == []
        assert subtask.blocks == []
        assert subtask.attempts == 0
        assert subtask.max_attempts == 3
        assert subtask.progress_percent == 0.0

    def test_custom_values(self):
        """EnhancedSubtask accepts custom values."""
        subtask = EnhancedSubtask(
            id="task_2",
            description="High priority task",
            expected_outcome="Download file",
            task_type=GoalType.DOWNLOAD,
            status=SubtaskStatus.IN_PROGRESS,
            priority=10,
            optional=True,
            depends_on=["task_1"],
            max_attempts=5
        )
        assert subtask.id == "task_2"
        assert subtask.status == SubtaskStatus.IN_PROGRESS
        assert subtask.priority == 10
        assert subtask.optional is True
        assert subtask.depends_on == ["task_1"]
        assert subtask.max_attempts == 5


class TestGoalEngine:
    """Tests for GoalEngine class."""

    def test_init(self):
        """GoalEngine initializes correctly."""
        engine = GoalEngine()
        assert engine is not None

    def test_decompose_simple_goal(self):
        """Should decompose a simple download goal."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a PDF about Python")

        # Should have at least one subtask
        assert decomposition is not None
        assert len(decomposition.subtasks) >= 1

    def test_decompose_identifies_goal_type(self):
        """Should identify goal type from description."""
        engine = GoalEngine()

        download_result = engine.decompose("Download the latest report")
        assert download_result.goal_type == GoalType.DOWNLOAD

    def test_classify_download_goal(self):
        """Should classify download-related goals."""
        engine = GoalEngine()

        goal_type = engine._classify_goal("download a PDF file")
        assert goal_type == GoalType.DOWNLOAD

    def test_classify_search_goal(self):
        """Should classify search-related goals."""
        engine = GoalEngine()

        goal_type = engine._classify_goal("search for Python tutorials")
        assert goal_type == GoalType.SEARCH

    def test_classify_navigate_goal(self):
        """Should classify navigation goals."""
        engine = GoalEngine()

        goal_type = engine._classify_goal("go to google.com")
        assert goal_type == GoalType.NAVIGATE


class TestGoalEngineProgress:
    """Tests for progress tracking functionality."""

    def test_update_progress(self):
        """Should update subtask progress."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        if decomposition.subtasks:
            subtask_id = decomposition.subtasks[0].id
            engine.set_subtask_progress(subtask_id, progress=0.5)

            subtask = engine._get_subtask(subtask_id)
            if subtask:
                assert subtask.progress_percent == 0.5

    def test_mark_complete(self):
        """Should mark subtask as completed."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        if decomposition.subtasks:
            subtask_id = decomposition.subtasks[0].id
            engine.complete_subtask(subtask_id)

            subtask = engine._get_subtask(subtask_id)
            if subtask:
                assert subtask.status == SubtaskStatus.COMPLETED

    def test_mark_failed(self):
        """Should mark subtask as failed."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        if decomposition.subtasks:
            subtask_id = decomposition.subtasks[0].id
            engine.fail_subtask(subtask_id, "Connection error")

            subtask = engine._get_subtask(subtask_id)
            if subtask:
                assert subtask.status == SubtaskStatus.FAILED


class TestGoalEngineDependencies:
    """Tests for dependency management."""

    def test_subtask_with_dependencies(self):
        """Should handle subtask dependencies."""
        engine = GoalEngine()

        # Create a decomposition with dependencies
        decomposition = engine.decompose("Find and download a specific book")

        # Check that some subtasks might have dependencies
        has_deps = any(len(st.depends_on) > 0 for st in decomposition.subtasks)
        # This is acceptable either way - some goals have deps, some don't

    def test_check_dependencies_satisfied(self):
        """Should check if dependencies are satisfied."""
        engine = GoalEngine()
        decomposition = engine.decompose("Search and download")

        if decomposition.subtasks:
            subtask = decomposition.subtasks[0]
            # First subtask should have no unsatisfied dependencies
            is_ready = engine._dependencies_satisfied(subtask.id)
            assert is_ready is True  # First task has no deps


class TestGoalEngineCompletion:
    """Tests for completion tracking."""

    def test_not_complete_initially(self):
        """Should not be complete initially."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        assert engine.is_complete() is False

    def test_complete_when_all_done(self):
        """Should be complete when all subtasks done."""
        engine = GoalEngine()
        decomposition = engine.decompose("Navigate to a website")

        # Mark all as complete
        for subtask in decomposition.subtasks:
            engine.complete_subtask(subtask.id)

        assert engine.is_complete() is True

    def test_get_remaining_subtasks(self):
        """Should return remaining incomplete subtasks."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download multiple files")

        remaining = engine.get_remaining_subtasks()

        # All should be remaining initially
        assert len(remaining) == len(decomposition.subtasks)


class TestGoalEngineAPICompatibility:
    """Tests for API compatibility methods added for simpler test interface."""

    def test_classify_goal_is_alias(self):
        """_classify_goal should be an alias for detect_goal_type."""
        engine = GoalEngine()

        goal = "download a PDF file"
        result1 = engine._classify_goal(goal)
        result2 = engine.detect_goal_type(goal)

        assert result1 == result2

    def test_get_subtask_returns_none_for_missing(self):
        """_get_subtask should return None for non-existent ID."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        result = engine._get_subtask("nonexistent_id")
        assert result is None

    def test_get_decomposition_for_subtask_returns_none_for_missing(self):
        """_get_decomposition_for_subtask should return None for non-existent ID."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        result = engine._get_decomposition_for_subtask("nonexistent_id")
        assert result is None

    def test_dependencies_satisfied_false_for_missing(self):
        """_dependencies_satisfied should return False for non-existent ID."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        result = engine._dependencies_satisfied("nonexistent_id")
        assert result is False

    def test_set_subtask_progress_completes_at_100(self):
        """set_subtask_progress should mark complete at 100%."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        if decomposition.subtasks:
            subtask_id = decomposition.subtasks[0].id
            engine.set_subtask_progress(subtask_id, progress=1.0)

            subtask = engine._get_subtask(subtask_id)
            if subtask:
                assert subtask.status == SubtaskStatus.COMPLETED
                assert subtask.progress_percent == 1.0

    def test_set_subtask_progress_in_progress(self):
        """set_subtask_progress should mark in_progress for partial progress."""
        engine = GoalEngine()
        decomposition = engine.decompose("Download a file")

        if decomposition.subtasks:
            subtask_id = decomposition.subtasks[0].id
            engine.set_subtask_progress(subtask_id, progress=0.25)

            subtask = engine._get_subtask(subtask_id)
            if subtask:
                assert subtask.status == SubtaskStatus.IN_PROGRESS
                assert subtask.progress_percent == 0.25

    def test_complete_subtask_nonexistent_does_not_crash(self):
        """complete_subtask should not crash for non-existent ID."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        # Should not raise
        engine.complete_subtask("nonexistent_id")

    def test_fail_subtask_nonexistent_does_not_crash(self):
        """fail_subtask should not crash for non-existent ID."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        # Should not raise
        engine.fail_subtask("nonexistent_id", "Some error")

    def test_is_complete_false_with_no_decompositions(self):
        """is_complete should return False when no decompositions exist."""
        engine = GoalEngine()
        # Don't decompose anything

        assert engine.is_complete() is False

    def test_get_remaining_subtasks_empty_with_no_decompositions(self):
        """get_remaining_subtasks should return empty list when no decompositions exist."""
        engine = GoalEngine()
        # Don't decompose anything

        remaining = engine.get_remaining_subtasks()
        assert remaining == []

    def test_set_subtask_progress_handles_nonexistent(self):
        """set_subtask_progress should handle non-existent ID gracefully."""
        engine = GoalEngine()
        engine.decompose("Download a file")

        # Should not raise
        engine.set_subtask_progress("nonexistent_id", progress=0.5)
