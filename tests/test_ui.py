"""
Unit tests for blackreach/ui.py

Tests UI components that can be unit tested without requiring
actual console interaction.
"""

import pytest
from unittest.mock import MagicMock, patch
from blackreach.ui import (
    Theme,
    SlashCompleter,
    AgentProgress,
    theme,
    HISTORY_FILE,
)


class TestTheme:
    """Tests for Theme dataclass."""

    def test_theme_has_primary_color(self):
        """Theme has primary color defined."""
        t = Theme()
        assert t.primary is not None
        assert isinstance(t.primary, str)

    def test_theme_has_error_color(self):
        """Theme has error color defined."""
        t = Theme()
        assert t.error is not None
        assert t.error != ""

    def test_theme_has_success_color(self):
        """Theme has success color defined."""
        t = Theme()
        assert t.success is not None

    def test_theme_has_warning_color(self):
        """Theme has warning color defined."""
        t = Theme()
        assert t.warning is not None

    def test_theme_has_muted_color(self):
        """Theme has muted color defined."""
        t = Theme()
        assert t.muted is not None

    def test_theme_has_highlight_color(self):
        """Theme has highlight color defined."""
        t = Theme()
        assert t.highlight is not None

    def test_theme_has_secondary_color(self):
        """Theme has secondary color defined."""
        t = Theme()
        assert t.secondary is not None

    def test_global_theme_exists(self):
        """Global theme instance exists."""
        assert theme is not None
        assert isinstance(theme, Theme)


class TestSlashCompleter:
    """Tests for SlashCompleter class."""

    def test_completer_has_commands(self):
        """SlashCompleter has commands defined."""
        completer = SlashCompleter()
        assert len(completer.commands) > 0

    def test_completer_has_help_command(self):
        """SlashCompleter has /help command."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        assert "/help" in cmd_names

    def test_completer_has_quit_command(self):
        """SlashCompleter has /quit command."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        assert "/quit" in cmd_names

    def test_completer_has_model_command(self):
        """SlashCompleter has /model command."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        assert "/model" in cmd_names

    def test_completer_has_status_command(self):
        """SlashCompleter has /status command."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        assert "/status" in cmd_names

    def test_completer_has_clear_command(self):
        """SlashCompleter has /clear command."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        assert "/clear" in cmd_names

    def test_completer_commands_have_descriptions(self):
        """All commands have descriptions."""
        completer = SlashCompleter()
        for cmd, desc in completer.commands:
            assert desc is not None
            assert len(desc) > 0

    def test_completer_commands_start_with_slash(self):
        """All commands start with /."""
        completer = SlashCompleter()
        for cmd, desc in completer.commands:
            assert cmd.startswith("/")

    def test_completer_has_shortcuts(self):
        """SlashCompleter has shortcut commands."""
        completer = SlashCompleter()
        cmd_names = [cmd for cmd, desc in completer.commands]
        # Check for shortcuts
        assert "/h" in cmd_names  # /help shortcut
        assert "/q" in cmd_names  # /quit shortcut
        assert "/m" in cmd_names  # /model shortcut

    def test_get_completions_with_slash(self):
        """get_completions returns results for /h prefix."""
        completer = SlashCompleter()

        # Mock document
        document = MagicMock()
        document.text_before_cursor = "/h"

        completions = list(completer.get_completions(document, None))

        # Should have /help and /h and /history
        assert len(completions) >= 2

    def test_get_completions_partial_match(self):
        """get_completions filters by prefix."""
        completer = SlashCompleter()

        document = MagicMock()
        document.text_before_cursor = "/qu"

        completions = list(completer.get_completions(document, None))

        # Should only have /quit
        assert len(completions) == 1
        assert completions[0].text == "/quit"

    def test_get_completions_no_match(self):
        """get_completions returns empty for non-matching prefix."""
        completer = SlashCompleter()

        document = MagicMock()
        document.text_before_cursor = "/xyz"

        completions = list(completer.get_completions(document, None))

        assert len(completions) == 0

    def test_get_completions_empty_returns_all(self):
        """get_completions returns all commands for empty input."""
        completer = SlashCompleter()

        document = MagicMock()
        document.text_before_cursor = ""

        completions = list(completer.get_completions(document, None))

        # Should return all commands
        assert len(completions) == len(completer.commands)


class TestAgentProgress:
    """Tests for AgentProgress class."""

    def test_init_state(self):
        """AgentProgress initializes with correct state."""
        progress = AgentProgress()
        assert progress.current_step == 0
        assert progress.max_steps == 0
        assert progress.current_phase == ""
        assert progress.last_action == ""

    def test_has_live_attribute(self):
        """AgentProgress has live attribute."""
        progress = AgentProgress()
        assert hasattr(progress, 'live')
        assert progress.live is None

    def test_has_step_shown_set(self):
        """AgentProgress has _step_shown set."""
        progress = AgentProgress()
        assert hasattr(progress, '_step_shown')
        assert isinstance(progress._step_shown, set)


class TestHistoryFile:
    """Tests for history file configuration."""

    def test_history_file_path_defined(self):
        """HISTORY_FILE path is defined."""
        assert HISTORY_FILE is not None

    def test_history_file_in_home_dir(self):
        """HISTORY_FILE is in home directory."""
        assert ".blackreach" in str(HISTORY_FILE)

    def test_history_file_named_history(self):
        """HISTORY_FILE is named 'history'."""
        assert HISTORY_FILE.name == "history"


class TestSlashCompleterIntegration:
    """Integration-style tests for SlashCompleter."""

    def test_completions_have_metadata(self):
        """Completions include display metadata."""
        completer = SlashCompleter()

        document = MagicMock()
        document.text_before_cursor = "/help"

        completions = list(completer.get_completions(document, None))

        for completion in completions:
            # All completions should have display_meta (description)
            assert completion.display_meta is not None

    def test_completions_have_correct_position(self):
        """Completions have correct start_position."""
        completer = SlashCompleter()

        document = MagicMock()
        document.text_before_cursor = "/he"

        completions = list(completer.get_completions(document, None))

        for completion in completions:
            # start_position should be negative length of typed text
            assert completion.start_position == -3  # len("/he")

    def test_case_insensitive_matching(self):
        """Completions are case insensitive."""
        completer = SlashCompleter()

        # Uppercase input
        document = MagicMock()
        document.text_before_cursor = "/HELP"

        completions = list(completer.get_completions(document, None))

        # Should match /help (lowercased)
        cmd_texts = [c.text for c in completions]
        assert "/help" in cmd_texts


class TestThemeColors:
    """Tests for specific theme color values."""

    def test_primary_is_cyan(self):
        """Primary color is cyan."""
        assert theme.primary == "cyan"

    def test_error_is_red(self):
        """Error color is red."""
        assert theme.error == "red"

    def test_success_is_green(self):
        """Success color is green."""
        assert theme.success == "green"

    def test_warning_is_yellow(self):
        """Warning color is yellow."""
        assert theme.warning == "yellow"
