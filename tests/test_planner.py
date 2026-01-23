"""
Unit tests for blackreach/planner.py

Tests for goal complexity detection and plan data structures.
Note: Full plan generation tests require LLM mocking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from blackreach.planner import Planner, Plan, Subtask
from blackreach.llm import LLMConfig


class TestSubtaskDataclass:
    """Tests for Subtask dataclass."""

    def test_subtask_required_fields(self):
        """Subtask has required fields."""
        subtask = Subtask(
            description="Go to example.com",
            expected_outcome="On example homepage"
        )
        assert subtask.description == "Go to example.com"
        assert subtask.expected_outcome == "On example homepage"

    def test_subtask_optional_default(self):
        """Subtask optional defaults to False."""
        subtask = Subtask(
            description="test",
            expected_outcome="result"
        )
        assert subtask.optional is False

    def test_subtask_optional_true(self):
        """Subtask can be marked optional."""
        subtask = Subtask(
            description="test",
            expected_outcome="result",
            optional=True
        )
        assert subtask.optional is True


class TestPlanDataclass:
    """Tests for Plan dataclass."""

    def test_plan_has_required_fields(self):
        """Plan has required fields."""
        plan = Plan(
            goal="Download papers",
            subtasks=[],
            estimated_steps=10
        )
        assert plan.goal == "Download papers"
        assert plan.subtasks == []
        assert plan.estimated_steps == 10

    def test_plan_with_subtasks(self):
        """Plan can contain subtasks."""
        subtask1 = Subtask("Go to arxiv", "On arxiv")
        subtask2 = Subtask("Search", "Results shown")
        plan = Plan(
            goal="Find papers",
            subtasks=[subtask1, subtask2],
            estimated_steps=5
        )
        assert len(plan.subtasks) == 2
        assert plan.subtasks[0].description == "Go to arxiv"


class TestPlannerIsSimpleGoal:
    """Tests for is_simple_goal method."""

    @patch('blackreach.planner.LLM')
    def test_simple_go_to(self, mock_llm):
        """'go to' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("go to wikipedia") is True

    @patch('blackreach.planner.LLM')
    def test_simple_navigate_to(self, mock_llm):
        """'navigate to' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("navigate to google.com") is True

    @patch('blackreach.planner.LLM')
    def test_simple_search_for(self, mock_llm):
        """'search for' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("search for cats") is True

    @patch('blackreach.planner.LLM')
    def test_simple_find(self, mock_llm):
        """'find' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("find wikipedia article") is True

    @patch('blackreach.planner.LLM')
    def test_simple_click(self, mock_llm):
        """'click' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("click the login button") is True

    @patch('blackreach.planner.LLM')
    def test_simple_open(self, mock_llm):
        """'open' goals are simple."""
        planner = Planner()
        assert planner.is_simple_goal("open github") is True

    @patch('blackreach.planner.LLM')
    def test_complex_download(self, mock_llm):
        """'download' goals are complex."""
        planner = Planner()
        assert planner.is_simple_goal("download this file") is False

    @patch('blackreach.planner.LLM')
    def test_complex_all(self, mock_llm):
        """'all' goals are complex (implies iteration)."""
        planner = Planner()
        assert planner.is_simple_goal("find all papers") is False

    @patch('blackreach.planner.LLM')
    def test_complex_multiple(self, mock_llm):
        """'multiple' goals are complex."""
        planner = Planner()
        assert planner.is_simple_goal("find multiple images") is False

    @patch('blackreach.planner.LLM')
    def test_complex_papers(self, mock_llm):
        """'papers' goals are complex (academic)."""
        planner = Planner()
        assert planner.is_simple_goal("get papers about AI") is False

    @patch('blackreach.planner.LLM')
    def test_complex_sequential(self, mock_llm):
        """'then' goals are complex (sequential)."""
        planner = Planner()
        assert planner.is_simple_goal("go to google then search for cats") is False

    @patch('blackreach.planner.LLM')
    def test_complex_and_then(self, mock_llm):
        """'and then' goals are complex."""
        planner = Planner()
        assert planner.is_simple_goal("open the page and then click login") is False

    @patch('blackreach.planner.LLM')
    def test_complex_number_greater_than_one(self, mock_llm):
        """Goals with numbers > 1 are complex."""
        planner = Planner()
        assert planner.is_simple_goal("find 5 articles") is False
        assert planner.is_simple_goal("download 10 files") is False

    @patch('blackreach.planner.LLM')
    def test_simple_short_goal(self, mock_llm):
        """Short goals default to simple."""
        planner = Planner()
        assert planner.is_simple_goal("visit example.com") is True

    @patch('blackreach.planner.LLM')
    def test_case_insensitive(self, mock_llm):
        """Goal detection is case insensitive."""
        planner = Planner()
        assert planner.is_simple_goal("GO TO WIKIPEDIA") is True
        assert planner.is_simple_goal("DOWNLOAD files") is False


class TestPlannerInit:
    """Tests for Planner initialization."""

    @patch('blackreach.planner.LLM')
    def test_init_creates_llm(self, mock_llm):
        """Planner creates LLM instance."""
        planner = Planner()
        mock_llm.assert_called_once()

    @patch('blackreach.planner.LLM')
    def test_init_with_custom_config(self, mock_llm):
        """Planner accepts custom LLM config."""
        config = LLMConfig(provider="openai", model="gpt-4")
        planner = Planner(llm_config=config)
        mock_llm.assert_called_once_with(config)


class TestPlannerPrompt:
    """Tests for planner prompt template."""

    def test_prompt_contains_goal_placeholder(self):
        """Prompt template has goal placeholder."""
        assert "{goal}" in Planner.PLAN_PROMPT

    def test_prompt_specifies_json_format(self):
        """Prompt requests JSON output."""
        assert "JSON" in Planner.PLAN_PROMPT
        assert "subtasks" in Planner.PLAN_PROMPT

    def test_prompt_has_rules(self):
        """Prompt includes planning rules."""
        assert "RULES" in Planner.PLAN_PROMPT


class TestPlannerPlan:
    """Tests for plan method with mocked LLM."""

    @patch('blackreach.planner.LLM')
    def test_plan_returns_none_for_simple_goal(self, mock_llm_class):
        """plan() returns None for simple goals."""
        planner = Planner()
        plan = planner.plan("go to wikipedia")
        assert plan is None

    @patch('blackreach.planner.LLM')
    def test_plan_parses_valid_json(self, mock_llm_class):
        """plan() parses valid JSON response for complex goals."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '''{
            "subtasks": [
                {"description": "Go to example.com", "expected_outcome": "On page"}
            ],
            "estimated_total_steps": 3
        }'''
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        # Use a complex goal (contains "download" which makes it complex)
        plan = planner.plan("download 5 papers from arxiv about transformers")

        assert plan is not None
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].description == "Go to example.com"

    @patch('blackreach.planner.LLM')
    def test_plan_handles_invalid_json(self, mock_llm_class):
        """plan() handles invalid JSON gracefully."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "This is not valid JSON at all"
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        # Use a complex goal (contains "all")
        plan = planner.plan("find all images of cats and save them")

        # Should return a default plan, not crash
        assert plan is not None
        assert len(plan.subtasks) >= 1

    @patch('blackreach.planner.LLM')
    def test_plan_extracts_json_from_text(self, mock_llm_class):
        """plan() extracts JSON from surrounding text."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '''Here's my analysis:
        {"subtasks": [{"description": "Step 1", "expected_outcome": "Done"}], "estimated_total_steps": 1}
        This is a simple plan.'''
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        # Use a complex goal (contains "multiple")
        plan = planner.plan("collect multiple datasets from kaggle")

        assert plan is not None
        assert len(plan.subtasks) == 1

    @patch('blackreach.planner.LLM')
    def test_plan_handles_optional_subtasks(self, mock_llm_class):
        """plan() handles optional subtasks."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '''{
            "subtasks": [
                {"description": "Step 1", "expected_outcome": "Done", "optional": true},
                {"description": "Step 2", "expected_outcome": "Done", "optional": false}
            ],
            "estimated_total_steps": 5
        }'''
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        plan = planner.plan("download files and also try to get metadata")

        assert plan is not None
        assert plan.subtasks[0].optional is True
        assert plan.subtasks[1].optional is False

    @patch('blackreach.planner.LLM')
    def test_plan_handles_invalid_json(self, mock_llm_class):
        """plan() handles invalid JSON with fallback plan."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = 'This is not valid JSON at all'
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        plan = planner.plan("download all papers from arxiv")

        # Should get fallback plan
        assert plan is not None
        assert len(plan.subtasks) >= 1
        assert "Complete:" in plan.subtasks[0].description

    @patch('blackreach.planner.LLM')
    def test_plan_handles_json_decode_error(self, mock_llm_class):
        """plan() handles JSONDecodeError with fallback plan."""
        mock_llm = MagicMock()
        # This has braces so regex finds it, but invalid JSON inside
        mock_llm.generate.return_value = '{not valid json syntax}'
        mock_llm_class.return_value = mock_llm

        planner = Planner()
        plan = planner.plan("download all files from the server")

        # Should get fallback plan from JSONDecodeError handler
        assert plan is not None
        assert len(plan.subtasks) >= 1
        assert "Complete:" in plan.subtasks[0].description


class TestFormatPlan:
    """Tests for plan formatting."""

    def test_format_plan_basic(self):
        """format_plan produces readable output."""
        plan = Plan(
            goal="Test goal",
            subtasks=[
                Subtask(description="Step 1", expected_outcome="Outcome 1"),
                Subtask(description="Step 2", expected_outcome="Outcome 2"),
            ],
            estimated_steps=10
        )

        planner = Planner()
        output = planner.format_plan(plan)

        assert "Test goal" in output
        assert "Step 1" in output
        assert "Outcome 1" in output
        assert "Estimated steps: ~10" in output

    def test_format_plan_with_optional(self):
        """format_plan marks optional steps."""
        plan = Plan(
            goal="Test with optional",
            subtasks=[
                Subtask(description="Required step", expected_outcome="Must do"),
                Subtask(description="Optional step", expected_outcome="Nice to have", optional=True),
            ],
            estimated_steps=5
        )

        planner = Planner()
        output = planner.format_plan(plan)

        assert "Required step" in output
        assert "(optional)" in output


class TestMaybePlan:
    """Tests for maybe_plan convenience function."""

    def test_maybe_plan_import(self):
        """maybe_plan can be imported."""
        from blackreach.planner import maybe_plan
        assert callable(maybe_plan)

    def test_maybe_plan_simple_goal_returns_none(self):
        """maybe_plan returns None for simple goals."""
        from blackreach.planner import maybe_plan
        result = maybe_plan("search google")
        assert result is None
