"""
Blackreach Goal Decomposition Engine - Intelligent goal breakdown and tracking.

Enhances the basic planner with:
- Semantic goal understanding
- Progress tracking per subtask
- Dependency management
- Partial success handling
- Adaptive replanning on failures

Example usage:
    engine = GoalEngine()

    # Decompose a goal
    decomposition = engine.decompose("Download 3 papers about machine learning")

    # Execute with progress tracking
    for subtask in decomposition.subtasks:
        result = execute_subtask(subtask)
        engine.update_progress(subtask.id, result)

    # Check completion
    if engine.is_complete():
        print("Goal achieved!")
    else:
        # Get remaining work
        remaining = engine.get_remaining_subtasks()
"""

import re
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime

from blackreach.knowledge import find_best_sources, extract_subject


class SubtaskStatus(Enum):
    """Status of a subtask."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"  # Waiting on dependencies


class GoalType(Enum):
    """Types of goals for specialized handling."""
    DOWNLOAD = "download"           # Download files
    SEARCH = "search"               # Find information
    NAVIGATE = "navigate"           # Go to a specific site
    EXTRACT = "extract"             # Extract data from pages
    INTERACT = "interact"           # Fill forms, click buttons
    MULTI_STEP = "multi_step"       # Complex multi-phase tasks
    UNKNOWN = "unknown"


@dataclass
class EnhancedSubtask:
    """A subtask with full tracking capabilities."""
    id: str
    description: str
    expected_outcome: str
    task_type: GoalType
    status: SubtaskStatus = SubtaskStatus.PENDING
    priority: int = 5  # 1-10
    optional: bool = False

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # IDs of prerequisite subtasks
    blocks: List[str] = field(default_factory=list)      # IDs of subtasks this blocks

    # Progress tracking
    attempts: int = 0
    max_attempts: int = 3
    progress_percent: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Context for execution
    target_url: str = ""
    search_query: str = ""
    selectors: List[str] = field(default_factory=list)
    expected_count: int = 1  # For download tasks

    # Results
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def can_start(self, completed_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_ids for dep in self.depends_on)

    def increment_attempt(self):
        """Record an attempt."""
        self.attempts += 1
        if self.status == SubtaskStatus.PENDING:
            self.status = SubtaskStatus.IN_PROGRESS
            self.started_at = datetime.now().isoformat()

    def mark_complete(self, result: Dict = None):
        """Mark subtask as complete."""
        self.status = SubtaskStatus.COMPLETED
        self.progress_percent = 100.0
        self.completed_at = datetime.now().isoformat()
        if result:
            self.result = result

    def mark_failed(self, error: str = ""):
        """Mark subtask as failed."""
        self.status = SubtaskStatus.FAILED
        self.error = error

    def should_retry(self) -> bool:
        """Check if we should retry this subtask."""
        return (
            self.status == SubtaskStatus.FAILED and
            self.attempts < self.max_attempts and
            not self.optional
        )


@dataclass
class GoalDecomposition:
    """A decomposed goal with subtasks and tracking."""
    id: str
    original_goal: str
    goal_type: GoalType
    subtasks: List[EnhancedSubtask]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Overall progress
    total_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0

    # Success criteria
    min_success_ratio: float = 0.8  # Need 80% success for goal completion
    target_downloads: int = 0       # For download goals

    # Metadata
    estimated_steps: int = 0
    actual_steps: int = 0
    search_subject: str = ""

    def __post_init__(self):
        self.total_subtasks = len(self.subtasks)

    @property
    def progress_percent(self) -> float:
        """Overall progress percentage."""
        if self.total_subtasks == 0:
            return 0.0
        completed = sum(1 for st in self.subtasks if st.status == SubtaskStatus.COMPLETED)
        return (completed / self.total_subtasks) * 100

    @property
    def is_complete(self) -> bool:
        """Check if goal is achieved."""
        completed = sum(1 for st in self.subtasks if st.status == SubtaskStatus.COMPLETED)
        required = sum(1 for st in self.subtasks if not st.optional)

        if required == 0:
            return completed > 0

        success_ratio = completed / max(required, 1)
        return success_ratio >= self.min_success_ratio

    def get_next_subtask(self) -> Optional[EnhancedSubtask]:
        """Get the next subtask to execute."""
        completed_ids = {st.id for st in self.subtasks if st.status == SubtaskStatus.COMPLETED}

        for subtask in self.subtasks:
            if subtask.status in [SubtaskStatus.PENDING, SubtaskStatus.BLOCKED]:
                if subtask.can_start(completed_ids):
                    return subtask
            elif subtask.status == SubtaskStatus.FAILED and subtask.should_retry():
                return subtask

        return None

    def get_remaining_subtasks(self) -> List[EnhancedSubtask]:
        """Get all subtasks that still need work."""
        return [
            st for st in self.subtasks
            if st.status not in [SubtaskStatus.COMPLETED, SubtaskStatus.SKIPPED]
        ]


class GoalEngine:
    """
    Intelligent goal decomposition and tracking engine.

    Features:
    - Semantic goal understanding
    - Automatic subtask generation
    - Progress tracking
    - Adaptive replanning
    """

    # Patterns for goal type detection
    GOAL_PATTERNS = {
        GoalType.DOWNLOAD: [
            r"download",
            r"get\s+(me\s+)?(a\s+)?(\d+\s+)?(file|paper|book|ebook|image|pdf|epub)",
            r"save",
            r"fetch",
        ],
        GoalType.SEARCH: [
            r"search\s+for",
            r"find\s+(information|info|data)",
            r"look\s+up",
            r"research",
        ],
        GoalType.NAVIGATE: [
            r"go\s+to",
            r"navigate\s+to",
            r"visit",
            r"open",
        ],
        GoalType.EXTRACT: [
            r"extract",
            r"scrape",
            r"get\s+(the\s+)?(text|content|data)",
            r"copy",
        ],
        GoalType.INTERACT: [
            r"fill",
            r"submit",
            r"click",
            r"sign\s+(up|in)",
            r"login",
        ],
    }

    def __init__(self, llm=None):
        self.llm = llm
        self._decompositions: Dict[str, GoalDecomposition] = {}
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[GoalType, List[re.Pattern]]:
        """Compile regex patterns for performance."""
        compiled = {}
        for goal_type, patterns in self.GOAL_PATTERNS.items():
            compiled[goal_type] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return compiled

    def _generate_id(self, text: str) -> str:
        """Generate a unique ID for a goal/subtask."""
        return hashlib.md5(f"{text}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

    def detect_goal_type(self, goal: str) -> GoalType:
        """Detect the type of goal."""
        for goal_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(goal):
                    return goal_type
        return GoalType.UNKNOWN

    def extract_quantity(self, goal: str) -> int:
        """Extract quantity from goal (e.g., 'download 5 papers' -> 5)."""
        # Look for explicit numbers
        numbers = re.findall(r'\b(\d+)\b', goal)
        if numbers:
            return int(numbers[0])

        # Look for words
        word_numbers = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "a few": 3, "some": 3, "several": 5, "many": 10,
        }
        goal_lower = goal.lower()
        for word, num in word_numbers.items():
            if word in goal_lower:
                return num

        return 1  # Default to 1

    def decompose(self, goal: str) -> GoalDecomposition:
        """
        Decompose a goal into subtasks.

        Returns a GoalDecomposition with all subtasks and tracking.
        """
        goal_id = self._generate_id(goal)
        goal_type = self.detect_goal_type(goal)
        quantity = self.extract_quantity(goal)
        subject = extract_subject(goal)

        # Generate subtasks based on goal type
        if goal_type == GoalType.DOWNLOAD:
            subtasks = self._decompose_download_goal(goal, quantity, subject)
        elif goal_type == GoalType.SEARCH:
            subtasks = self._decompose_search_goal(goal, subject)
        elif goal_type == GoalType.NAVIGATE:
            subtasks = self._decompose_navigate_goal(goal)
        else:
            subtasks = self._decompose_generic_goal(goal)

        decomposition = GoalDecomposition(
            id=goal_id,
            original_goal=goal,
            goal_type=goal_type,
            subtasks=subtasks,
            target_downloads=quantity if goal_type == GoalType.DOWNLOAD else 0,
            estimated_steps=sum(3 for _ in subtasks),  # Estimate 3 steps per subtask
            search_subject=subject,
        )

        self._decompositions[goal_id] = decomposition
        return decomposition

    def _decompose_download_goal(
        self,
        goal: str,
        quantity: int,
        subject: str
    ) -> List[EnhancedSubtask]:
        """Decompose a download goal into subtasks."""
        subtasks = []

        # Find best sources for this content
        sources = find_best_sources(goal, max_sources=3)

        # Subtask 1: Navigate to best source
        if sources:
            source = sources[0]
            nav_task = EnhancedSubtask(
                id=self._generate_id("navigate"),
                description=f"Navigate to {source.name}",
                expected_outcome=f"On {source.name} homepage or search page",
                task_type=GoalType.NAVIGATE,
                priority=10,
                target_url=source.url,
            )
            subtasks.append(nav_task)

            # Subtask 2: Search for content
            search_task = EnhancedSubtask(
                id=self._generate_id("search"),
                description=f"Search for '{subject}'",
                expected_outcome="Search results displayed",
                task_type=GoalType.SEARCH,
                priority=9,
                depends_on=[nav_task.id],
                search_query=subject,
            )
            subtasks.append(search_task)

            # Subtask 3+: Download each item
            for i in range(quantity):
                download_task = EnhancedSubtask(
                    id=self._generate_id(f"download_{i}"),
                    description=f"Download item {i+1} of {quantity}",
                    expected_outcome=f"File {i+1} downloaded successfully",
                    task_type=GoalType.DOWNLOAD,
                    priority=8 - i,  # Decreasing priority
                    depends_on=[search_task.id],
                    expected_count=1,
                    optional=i >= 1,  # First download required, rest optional
                )
                subtasks.append(download_task)

        else:
            # Fallback: generic download task
            subtasks.append(EnhancedSubtask(
                id=self._generate_id("download"),
                description=f"Download {quantity} items matching '{subject}'",
                expected_outcome=f"{quantity} files downloaded",
                task_type=GoalType.DOWNLOAD,
                priority=10,
                expected_count=quantity,
            ))

        return subtasks

    def _decompose_search_goal(
        self,
        goal: str,
        subject: str
    ) -> List[EnhancedSubtask]:
        """Decompose a search goal into subtasks."""
        subtasks = []

        # Find relevant sources
        sources = find_best_sources(goal, max_sources=2)

        if sources:
            source = sources[0]
            nav_task = EnhancedSubtask(
                id=self._generate_id("navigate"),
                description=f"Navigate to {source.name}",
                expected_outcome=f"On {source.name}",
                task_type=GoalType.NAVIGATE,
                priority=10,
                target_url=source.url,
            )
            subtasks.append(nav_task)

            search_task = EnhancedSubtask(
                id=self._generate_id("search"),
                description=f"Search for '{subject}'",
                expected_outcome="Relevant results found",
                task_type=GoalType.SEARCH,
                priority=9,
                depends_on=[nav_task.id],
                search_query=subject,
            )
            subtasks.append(search_task)

            review_task = EnhancedSubtask(
                id=self._generate_id("review"),
                description="Review and extract relevant information",
                expected_outcome="Information gathered",
                task_type=GoalType.EXTRACT,
                priority=8,
                depends_on=[search_task.id],
            )
            subtasks.append(review_task)

        else:
            # Google search fallback
            subtasks.append(EnhancedSubtask(
                id=self._generate_id("search"),
                description=f"Search Google for '{subject}'",
                expected_outcome="Search results displayed",
                task_type=GoalType.SEARCH,
                priority=10,
                target_url="https://www.google.com",
                search_query=subject,
            ))

        return subtasks

    def _decompose_navigate_goal(self, goal: str) -> List[EnhancedSubtask]:
        """Decompose a navigation goal."""
        # Extract URL from goal
        url_match = re.search(r'https?://\S+', goal)
        domain_match = re.search(r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}\b', goal)

        target_url = ""
        if url_match:
            target_url = url_match.group()
        elif domain_match:
            target_url = f"https://{domain_match.group()}"

        return [EnhancedSubtask(
            id=self._generate_id("navigate"),
            description=f"Navigate to {target_url or 'target site'}",
            expected_outcome="Page loaded successfully",
            task_type=GoalType.NAVIGATE,
            priority=10,
            target_url=target_url,
        )]

    def _decompose_generic_goal(self, goal: str) -> List[EnhancedSubtask]:
        """Decompose a generic goal."""
        return [EnhancedSubtask(
            id=self._generate_id("generic"),
            description=goal,
            expected_outcome="Goal completed",
            task_type=GoalType.UNKNOWN,
            priority=10,
        )]

    def update_progress(
        self,
        decomposition_id: str,
        subtask_id: str,
        status: SubtaskStatus,
        result: Dict = None,
        error: str = ""
    ) -> None:
        """Update progress for a subtask."""
        if decomposition_id not in self._decompositions:
            return

        decomposition = self._decompositions[decomposition_id]
        for subtask in decomposition.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                if result:
                    subtask.result = result
                if error:
                    subtask.error = error
                if status == SubtaskStatus.COMPLETED:
                    subtask.mark_complete(result)
                    decomposition.completed_subtasks += 1
                elif status == SubtaskStatus.FAILED:
                    decomposition.failed_subtasks += 1
                break

    def replan(self, decomposition_id: str) -> Optional[List[EnhancedSubtask]]:
        """
        Generate new subtasks for failed/blocked items.

        Returns new subtasks to try, or None if goal is unsalvageable.
        """
        if decomposition_id not in self._decompositions:
            return None

        decomposition = self._decompositions[decomposition_id]
        new_subtasks = []

        for subtask in decomposition.subtasks:
            if subtask.status == SubtaskStatus.FAILED and not subtask.should_retry():
                # Generate alternative approach
                if subtask.task_type == GoalType.DOWNLOAD:
                    # Try a different source
                    alt_task = EnhancedSubtask(
                        id=self._generate_id("alt_download"),
                        description=f"Alternative: {subtask.description}",
                        expected_outcome=subtask.expected_outcome,
                        task_type=GoalType.DOWNLOAD,
                        priority=subtask.priority - 1,
                        optional=True,
                    )
                    new_subtasks.append(alt_task)

        if new_subtasks:
            decomposition.subtasks.extend(new_subtasks)
            decomposition.total_subtasks = len(decomposition.subtasks)

        return new_subtasks if new_subtasks else None

    def get_summary(self, decomposition_id: str) -> Dict:
        """Get progress summary for a decomposition."""
        if decomposition_id not in self._decompositions:
            return {}

        d = self._decompositions[decomposition_id]
        return {
            "goal": d.original_goal,
            "goal_type": d.goal_type.value,
            "progress_percent": d.progress_percent,
            "is_complete": d.is_complete,
            "total_subtasks": d.total_subtasks,
            "completed": d.completed_subtasks,
            "failed": d.failed_subtasks,
            "remaining": len(d.get_remaining_subtasks()),
            "estimated_steps": d.estimated_steps,
            "actual_steps": d.actual_steps,
        }

    def format_plan(self, decomposition: GoalDecomposition) -> str:
        """Format decomposition for display."""
        lines = [
            f"Goal: {decomposition.original_goal}",
            f"Type: {decomposition.goal_type.value}",
            f"Progress: {decomposition.progress_percent:.0f}%",
            "",
            "Subtasks:",
        ]

        status_icons = {
            SubtaskStatus.PENDING: "○",
            SubtaskStatus.IN_PROGRESS: "◐",
            SubtaskStatus.COMPLETED: "●",
            SubtaskStatus.FAILED: "✗",
            SubtaskStatus.SKIPPED: "–",
            SubtaskStatus.BLOCKED: "◌",
        }

        for i, st in enumerate(decomposition.subtasks, 1):
            icon = status_icons.get(st.status, "?")
            optional = " (optional)" if st.optional else ""
            lines.append(f"  {icon} {i}. {st.description}{optional}")
            if st.status == SubtaskStatus.FAILED and st.error:
                lines.append(f"      Error: {st.error[:50]}")

        return "\n".join(lines)


# Global instance
_goal_engine: Optional[GoalEngine] = None


def get_goal_engine() -> GoalEngine:
    """Get or create the global goal engine."""
    global _goal_engine
    if _goal_engine is None:
        _goal_engine = GoalEngine()
    return _goal_engine
