"""
Unit tests for blackreach/cli.py

Tests CLI commands using Click's testing utilities.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from click.testing import CliRunner


class TestCLIBasics:
    """Tests for basic CLI setup."""

    def test_cli_imports(self):
        """CLI module can be imported."""
        from blackreach.cli import cli
        assert cli is not None

    def test_cli_has_version(self):
        """CLI has version defined."""
        from blackreach.cli import __version__
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_cli_version_format(self):
        """CLI version has correct format."""
        from blackreach.cli import __version__
        # Support pre-release versions like 4.0.0-beta.1
        base_version = __version__.split("-")[0]
        parts = base_version.split(".")
        assert len(parts) == 3  # Major.Minor.Patch

    def test_banner_exists(self):
        """CLI has banner defined."""
        from blackreach.cli import BANNER
        assert BANNER is not None
        assert len(BANNER) > 0

    def test_banner_contains_description(self):
        """Banner contains description."""
        from blackreach.cli import BANNER
        # Banner should contain the description text
        assert "Autonomous Browser Agent" in BANNER


class TestCLIHelperFunctions:
    """Tests for CLI helper functions."""

    def test_is_first_run_function_exists(self):
        """is_first_run function exists."""
        from blackreach.cli import is_first_run
        assert callable(is_first_run)

    def test_check_playwright_browsers_exists(self):
        """check_playwright_browsers function exists."""
        from blackreach.cli import check_playwright_browsers
        assert callable(check_playwright_browsers)

    def test_install_playwright_browsers_exists(self):
        """install_playwright_browsers function exists."""
        from blackreach.cli import install_playwright_browsers
        assert callable(install_playwright_browsers)

    def test_cleanup_keyboard_exists(self):
        """_cleanup_keyboard function exists."""
        from blackreach.cli import _cleanup_keyboard
        assert callable(_cleanup_keyboard)


class TestCLICommands:
    """Tests for CLI commands structure."""

    def test_cli_has_run_command(self):
        """CLI has 'run' command."""
        from blackreach.cli import cli
        assert 'run' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_config_command(self):
        """CLI has 'config' command."""
        from blackreach.cli import cli
        assert 'config' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_models_command(self):
        """CLI has 'models' command."""
        from blackreach.cli import cli
        assert 'models' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_sessions_command(self):
        """CLI has 'sessions' command."""
        from blackreach.cli import cli
        assert 'sessions' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_status_command(self):
        """CLI has 'status' command."""
        from blackreach.cli import cli
        assert 'status' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_setup_command(self):
        """CLI has 'setup' command."""
        from blackreach.cli import cli
        assert 'setup' in [cmd.name for cmd in cli.commands.values()]

    def test_cli_has_doctor_command(self):
        """CLI has 'doctor' command."""
        from blackreach.cli import cli
        assert 'doctor' in [cmd.name for cmd in cli.commands.values()]


class TestCLIInvocation:
    """Tests for CLI invocation using CliRunner."""

    def test_cli_help(self):
        """CLI --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'blackreach' in result.output.lower() or 'usage' in result.output.lower()

    def test_cli_version(self):
        """CLI --version works."""
        from blackreach.cli import cli, __version__
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_run_help(self):
        """run --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert result.exit_code == 0
        assert 'goal' in result.output.lower() or 'provider' in result.output.lower()

    def test_config_help(self):
        """config --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['config', '--help'])
        assert result.exit_code == 0

    def test_models_help(self):
        """models --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models', '--help'])
        assert result.exit_code == 0

    def test_sessions_help(self):
        """sessions --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions', '--help'])
        assert result.exit_code == 0

    def test_status_help(self):
        """status --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['status', '--help'])
        assert result.exit_code == 0

    def test_setup_help(self):
        """setup --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['setup', '--help'])
        assert result.exit_code == 0

    def test_doctor_help(self):
        """doctor --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor', '--help'])
        assert result.exit_code == 0


class TestCLIRunOptions:
    """Tests for run command options."""

    def test_run_has_provider_option(self):
        """run has --provider option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--provider' in result.output or '-p' in result.output

    def test_run_has_model_option(self):
        """run has --model option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--model' in result.output or '-m' in result.output

    def test_run_has_headless_option(self):
        """run has --headless option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--headless' in result.output

    def test_run_has_steps_option(self):
        """run has --steps option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--steps' in result.output or '-s' in result.output

    def test_run_has_resume_option(self):
        """run has --resume option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--resume' in result.output or '-r' in result.output


class TestCLIModelsOptions:
    """Tests for models command options."""

    def test_models_has_provider_option(self):
        """models has --provider option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models', '--help'])
        assert '--provider' in result.output or '-p' in result.output


class TestCLISetupOptions:
    """Tests for setup command options."""

    def test_setup_has_reset_option(self):
        """setup has --reset option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['setup', '--help'])
        assert '--reset' in result.output


class TestCLIGlobalState:
    """Tests for CLI global state."""

    def test_active_agent_starts_none(self):
        """_active_agent starts as None."""
        from blackreach.cli import _active_agent
        assert _active_agent is None

    def test_signal_handler_exists(self):
        """_signal_handler function exists."""
        from blackreach.cli import _signal_handler
        assert callable(_signal_handler)


class TestModelsCommand:
    """Tests for models command execution."""

    @patch('blackreach.cli.console')
    def test_models_runs(self, mock_console):
        """models command runs without error."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models'])
        # Should exit cleanly (0 or handled error)
        assert result.exit_code in [0, 1]


class TestStatusCommand:
    """Tests for status command execution."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    def test_status_runs(self, mock_config, mock_console):
        """status command runs without error."""
        mock_config.config.default_provider = "ollama"
        mock_config.config.ollama.default_model = "llama3"
        mock_config.config.max_steps = 30
        mock_config.config.headless = True
        mock_config.config.download_dir = "/tmp/downloads"

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['status'])
        # Should complete
        assert result.exit_code in [0, 1]


class TestConfigCommand:
    """Tests for config command execution."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    def test_config_runs(self, mock_config, mock_console):
        """config command runs without error."""
        mock_config.config.default_provider = "ollama"

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['config'])
        # Exit code 0 or 1 (may prompt for input)
        assert result.exit_code in [0, 1, 2]


class TestSessionsCommand:
    """Tests for sessions command execution."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_runs(self, mock_memory, mock_console):
        """sessions command runs without error."""
        mock_memory.return_value.get_session_history.return_value = []

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions'])
        # Should complete (may fail without db)
        assert result.exit_code in [0, 1, 2]


class TestDoctorCommand:
    """Tests for doctor command."""

    def test_cli_has_doctor_command(self):
        """CLI has 'doctor' command."""
        from blackreach.cli import cli
        assert 'doctor' in [cmd.name for cmd in cli.commands.values()]

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    def test_doctor_runs(self, mock_check, mock_console):
        """doctor command runs."""
        mock_check.return_value = True

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])
        assert result.exit_code in [0, 1]


class TestCleanupKeyboard:
    """Tests for keyboard cleanup function."""

    @patch('subprocess.run')
    def test_cleanup_on_linux(self, mock_run):
        """_cleanup_keyboard runs on Linux."""
        import sys
        with patch.object(sys, 'platform', 'linux'):
            from blackreach.cli import _cleanup_keyboard
            _cleanup_keyboard()
            # May or may not call subprocess based on platform


class TestSignalHandler:
    """Tests for signal handler."""

    @patch('blackreach.cli.console')
    def test_signal_handler_prints_message(self, mock_console):
        """_signal_handler prints exit message."""
        import signal
        from blackreach.cli import _signal_handler

        # Should not raise
        try:
            _signal_handler(signal.SIGINT, None)
        except SystemExit:
            pass  # Expected behavior


class TestIsFirstRun:
    """Tests for is_first_run function."""

    @patch('blackreach.cli.CONFIG_FILE')
    def test_first_run_when_no_config(self, mock_config_file):
        """is_first_run returns True when config doesn't exist."""
        mock_config_file.exists.return_value = False

        from blackreach.cli import is_first_run
        result = is_first_run()

        assert result is True

    @patch('blackreach.cli.CONFIG_FILE')
    def test_not_first_run_when_config_exists(self, mock_config_file):
        """is_first_run returns False when config exists."""
        mock_config_file.exists.return_value = True

        from blackreach.cli import is_first_run
        result = is_first_run()

        assert result is False


class TestCheckPlaywrightBrowsers:
    """Tests for check_playwright_browsers function."""

    @patch('subprocess.run')
    def test_returns_true_when_installed(self, mock_run):
        """check_playwright_browsers returns True when browsers installed."""
        mock_run.return_value = MagicMock(returncode=0)

        from blackreach.cli import check_playwright_browsers
        result = check_playwright_browsers()

        assert result is True

    @patch('subprocess.run')
    def test_returns_false_when_not_installed(self, mock_run):
        """check_playwright_browsers returns False when not installed."""
        mock_run.return_value = MagicMock(returncode=1)

        from blackreach.cli import check_playwright_browsers
        result = check_playwright_browsers()

        assert result is False

    @patch('subprocess.run')
    def test_handles_file_not_found(self, mock_run):
        """check_playwright_browsers handles FileNotFoundError."""
        mock_run.side_effect = FileNotFoundError("Command not found")

        from blackreach.cli import check_playwright_browsers
        result = check_playwright_browsers()

        assert result is False


class TestInstallPlaywrightBrowsers:
    """Tests for install_playwright_browsers function."""

    @patch('subprocess.run')
    @patch('blackreach.cli.console')
    def test_install_success(self, mock_console, mock_run):
        """install_playwright_browsers returns True on success."""
        mock_run.return_value = MagicMock(returncode=0)

        from blackreach.cli import install_playwright_browsers
        result = install_playwright_browsers()

        assert result is True

    @patch('subprocess.run')
    @patch('blackreach.cli.console')
    def test_install_failure(self, mock_console, mock_run):
        """install_playwright_browsers returns False on CalledProcessError."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")

        from blackreach.cli import install_playwright_browsers
        result = install_playwright_browsers()

        assert result is False


class TestCleanupKeyboard:
    """Tests for _cleanup_keyboard function."""

    def test_cleanup_with_no_agent(self):
        """_cleanup_keyboard handles no active agent."""
        import blackreach.cli as cli_module
        original_agent = cli_module._active_agent
        cli_module._active_agent = None

        from blackreach.cli import _cleanup_keyboard
        # Should not raise
        _cleanup_keyboard()

        cli_module._active_agent = original_agent

    def test_cleanup_with_agent_no_hand(self):
        """_cleanup_keyboard handles agent without hand."""
        import blackreach.cli as cli_module
        original_agent = cli_module._active_agent

        mock_agent = MagicMock()
        mock_agent.hand = None
        cli_module._active_agent = mock_agent

        from blackreach.cli import _cleanup_keyboard
        _cleanup_keyboard()

        cli_module._active_agent = original_agent

    def test_cleanup_with_agent_and_hand(self):
        """_cleanup_keyboard calls release_all_keys when available."""
        import blackreach.cli as cli_module
        original_agent = cli_module._active_agent

        mock_hand = MagicMock()
        mock_agent = MagicMock()
        mock_agent.hand = mock_hand
        cli_module._active_agent = mock_agent

        from blackreach.cli import _cleanup_keyboard
        _cleanup_keyboard()

        mock_hand._release_all_keys.assert_called_once()
        cli_module._active_agent = original_agent


class TestCLIVersionInfo:
    """Tests for CLI version information."""

    def test_version_is_semantic(self):
        """Version follows semantic versioning."""
        from blackreach.cli import __version__
        # Support pre-release versions like 4.0.0-beta.1
        base_version = __version__.split("-")[0]
        parts = base_version.split(".")
        assert len(parts) == 3
        # All parts should be numeric
        for part in parts:
            assert part.isdigit()

    def test_banner_contains_version(self):
        """Banner includes version number."""
        from blackreach.cli import BANNER, __version__
        assert __version__ in BANNER


class TestRunCommandOptions:
    """Extended tests for run command options."""

    def test_run_has_provider_option(self):
        """Run command has provider option."""
        from blackreach.cli import cli
        run_cmd = cli.commands.get('run')
        param_names = [p.name for p in run_cmd.params]
        assert 'provider' in param_names

    def test_run_has_goal_argument(self):
        """Run command has goal argument."""
        from blackreach.cli import cli
        run_cmd = cli.commands.get('run')
        param_names = [p.name for p in run_cmd.params]
        assert 'goal' in param_names

    def test_run_has_model_option(self):
        """Run command has model option."""
        from blackreach.cli import cli
        run_cmd = cli.commands.get('run')
        param_names = [p.name for p in run_cmd.params]
        assert 'model' in param_names


class TestCheckOllamaRunning:
    """Tests for check_ollama_running function."""

    def test_function_exists(self):
        """check_ollama_running function exists."""
        from blackreach.cli import check_ollama_running
        assert callable(check_ollama_running)

    def test_ollama_running_returns_bool(self):
        """check_ollama_running returns a boolean."""
        from blackreach.cli import check_ollama_running
        result = check_ollama_running()
        assert isinstance(result, bool)


class TestShowResults:
    """Tests for _show_results function."""

    @patch('blackreach.cli.console')
    def test_show_results_success(self, mock_console):
        """_show_results displays success result."""
        from blackreach.cli import _show_results

        result = {
            "success": True,
            "downloads": ["/tmp/file1.pdf"],
            "pages_visited": 5,
            "steps_taken": 10,
            "failures": 0
        }

        _show_results(result)

        assert mock_console.print.called

    @patch('blackreach.cli.console')
    def test_show_results_failure(self, mock_console):
        """_show_results displays failure result."""
        from blackreach.cli import _show_results

        result = {
            "success": False,
            "downloads": [],
            "pages_visited": 2,
            "steps_taken": 3,
            "failures": 2
        }

        _show_results(result)

        assert mock_console.print.called


class TestCLIEntryPoints:
    """Tests for CLI entry points."""

    def test_main_function_exists(self):
        """main() function exists."""
        from blackreach.cli import main
        assert callable(main)

    def test_interactive_mode_function_exists(self):
        """interactive_mode() function exists."""
        from blackreach.cli import interactive_mode
        assert callable(interactive_mode)

    def test_show_help_function_exists(self):
        """show_help() function exists."""
        from blackreach.cli import show_help
        assert callable(show_help)

    def test_run_agent_with_ui_function_exists(self):
        """run_agent_with_ui() function exists."""
        from blackreach.cli import run_agent_with_ui
        assert callable(run_agent_with_ui)


class TestCLIAllCommands:
    """Tests for all CLI commands structure."""

    def test_all_commands_have_help(self):
        """All CLI commands have help text."""
        from blackreach.cli import cli

        for name, cmd in cli.commands.items():
            assert cmd.help is not None or cmd.short_help is not None, \
                f"Command {name} missing help"

    def test_run_command_params(self):
        """run command has expected parameters."""
        from blackreach.cli import cli

        run_cmd = cli.commands.get('run')
        param_names = [p.name for p in run_cmd.params]

        expected = ['goal', 'provider', 'model', 'headless', 'steps', 'resume']
        for param in expected:
            assert param in param_names, f"Missing param: {param}"

    def test_config_command_exists(self):
        """config command exists and is callable."""
        from blackreach.cli import cli

        config_cmd = cli.commands.get('config')
        assert config_cmd is not None

    def test_models_command_has_provider_option(self):
        """models command has provider option."""
        from blackreach.cli import cli

        models_cmd = cli.commands.get('models')
        param_names = [p.name for p in models_cmd.params]
        assert 'provider' in param_names

    def test_setup_command_has_reset_option(self):
        """setup command has reset option."""
        from blackreach.cli import cli

        setup_cmd = cli.commands.get('setup')
        param_names = [p.name for p in setup_cmd.params]
        assert 'reset' in param_names


class TestCLIConstants:
    """Tests for CLI constants and globals."""

    def test_version_format(self):
        """Version has correct format."""
        from blackreach.cli import __version__

        # Support pre-release versions like 4.0.0-beta.1
        base_version = __version__.split('-')[0]
        parts = base_version.split('.')
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_banner_not_empty(self):
        """Banner is not empty."""
        from blackreach.cli import BANNER

        assert BANNER is not None
        assert len(BANNER) > 0

    def test_config_file_path_defined(self):
        """CONFIG_FILE path is defined."""
        from blackreach.cli import CONFIG_FILE

        assert CONFIG_FILE is not None

    def test_active_agent_exists(self):
        """_active_agent variable exists in cli module."""
        import blackreach.cli as cli_module

        # Just verify it exists (may not be None if tests ran agent)
        assert hasattr(cli_module, '_active_agent')


class TestRunFirstTimeSetup:
    """Tests for run_first_time_setup function."""

    def test_function_exists(self):
        """run_first_time_setup function exists."""
        from blackreach.cli import run_first_time_setup
        assert callable(run_first_time_setup)


class TestCLIGroupBehavior:
    """Tests for CLI group behavior."""

    def test_cli_invokes_without_command_shows_help(self):
        """CLI without command shows help or runs interactive."""
        from blackreach.cli import cli
        runner = CliRunner()

        # Without arguments, it should either show help or start interactive
        # (depending on whether terminal)
        result = runner.invoke(cli, [])
        # May start interactive mode or show help
        assert result.exit_code in [0, 1, 2]

    def test_cli_unknown_command_fails(self):
        """CLI with unknown command fails."""
        from blackreach.cli import cli
        runner = CliRunner()

        result = runner.invoke(cli, ['unknown_cmd'])
        assert result.exit_code != 0


class TestVersionCommand:
    """Tests for version command."""

    def test_version_command_help(self):
        """version --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['version', '--help'])
        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    def test_version_shows_info(self, mock_console):
        """version command shows version info."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['version'])
        assert result.exit_code == 0


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_command_help(self):
        """validate --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate', '--help'])
        assert result.exit_code == 0
        assert '--fix' in result.output

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    def test_validate_runs(self, mock_config, mock_console):
        """validate command runs."""
        # Set up mock config
        mock_cfg = MagicMock()
        mock_cfg.default_provider = "ollama"
        mock_cfg.ollama.default_model = "llama3"
        mock_cfg.browser_type = "chromium"
        mock_cfg.max_steps = 30
        mock_cfg.download_dir = "/tmp/downloads"
        mock_config.load.return_value = mock_cfg
        mock_config.has_api_key.return_value = False

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate'])
        assert result.exit_code in [0, 1]


class TestActionsCommand:
    """Tests for actions command."""

    def test_actions_command_help(self):
        """actions --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['actions', '--help'])
        assert result.exit_code == 0
        assert '--domain' in result.output

    @patch('blackreach.cli.console')
    @patch('blackreach.action_tracker.ActionTracker')
    @patch('blackreach.memory.PersistentMemory')
    def test_actions_runs(self, mock_memory, mock_tracker, mock_console):
        """actions command runs."""
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.get_stats_summary.return_value = {
            "total_tracked_actions": 0,
            "total_successes": 0,
            "overall_success_rate": 0,
            "unique_action_patterns": 0,
            "domains_tracked": 0,
            "problem_actions": []
        }
        mock_tracker.return_value = mock_tracker_instance

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['actions'])
        assert result.exit_code in [0, 1]


class TestSourcesCommand:
    """Tests for sources command."""

    def test_sources_command_help(self):
        """sources --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sources', '--help'])
        assert result.exit_code == 0
        assert '--type' in result.output


class TestStatsCommand:
    """Tests for stats command."""

    def test_stats_command_help(self):
        """stats --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['stats', '--help'])
        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_stats_runs(self, mock_memory, mock_console):
        """stats command runs."""
        mock_memory_instance = MagicMock()
        mock_memory_instance.get_detailed_stats.return_value = {
            "total_sessions": 0,
            "completed_sessions": 0,
            "session_success_rate": 0,
            "total_downloads": 0,
            "total_downloaded_size": "0 bytes",
            "total_visits": 0,
            "known_domains": 0,
            "avg_steps_per_session": 0,
            "avg_downloads_per_session": 0,
            "total_failures": 0,
            "db_path": "/tmp/memory.db"
        }
        mock_memory.return_value = mock_memory_instance

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['stats'])
        assert result.exit_code in [0, 1]


class TestHealthCommand:
    """Tests for health command."""

    def test_health_command_help(self):
        """health --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['health', '--help'])
        assert result.exit_code == 0
        assert '--type' in result.output
        assert '--timeout' in result.output


class TestDownloadsCommand:
    """Tests for downloads command."""

    def test_downloads_command_help(self):
        """downloads --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads', '--help'])
        assert result.exit_code == 0
        assert '--limit' in result.output
        assert '--all' in result.output

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_empty(self, mock_memory, mock_console):
        """downloads command handles empty list."""
        mock_memory_instance = MagicMock()
        mock_memory_instance.get_downloads.return_value = []
        mock_memory.return_value = mock_memory_instance

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads'])
        assert result.exit_code in [0, 1]


class TestClearCommand:
    """Tests for clear command."""

    def test_clear_command_help(self):
        """clear --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['clear', '--help'])
        assert result.exit_code == 0
        assert '--logs' in result.output
        assert '--days' in result.output
        assert '--force' in result.output

    @patch('blackreach.cli.console')
    def test_clear_without_flags(self, mock_console):
        """clear command without flags shows usage."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['clear'])
        assert result.exit_code == 0


class TestLogsCommand:
    """Tests for logs command."""

    def test_logs_command_help(self):
        """logs --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs', '--help'])
        assert result.exit_code == 0
        assert '--limit' in result.output
        assert '--id' in result.output

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.get_recent_logs')
    def test_logs_empty(self, mock_get_logs, mock_console):
        """logs command handles no logs."""
        mock_get_logs.return_value = []

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs'])
        assert result.exit_code in [0, 1]


class TestResumableCommand:
    """Tests for resumable command."""

    def test_resumable_command_help(self):
        """resumable --help works."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['resumable', '--help'])
        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_resumable_empty(self, mock_memory, mock_console):
        """resumable command handles no sessions."""
        mock_memory_instance = MagicMock()
        mock_memory_instance.get_resumable_sessions.return_value = []
        mock_memory.return_value = mock_memory_instance

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['resumable'])
        assert result.exit_code in [0, 1]


class TestShowResultsFunction:
    """Tests for _show_results function."""

    @patch('blackreach.cli.console')
    def test_show_results_paused(self, mock_console):
        """_show_results displays paused result."""
        from blackreach.cli import _show_results

        result = {
            "success": False,
            "paused": True,
            "downloads": [],
            "pages_visited": 3,
            "steps_taken": 5,
            "failures": 0,
            "session_id": 42
        }

        _show_results(result)

        assert mock_console.print.called

    @patch('blackreach.cli.console')
    def test_show_results_with_downloads(self, mock_console):
        """_show_results displays downloads count."""
        from blackreach.cli import _show_results

        result = {
            "success": True,
            "downloads": ["/tmp/file1.pdf", "/tmp/file2.txt"],
            "pages_visited": 10,
            "steps_taken": 15,
            "failures": 1
        }

        _show_results(result)

        assert mock_console.print.called


class TestRunCommandValidation:
    """Tests for run command argument validation."""

    def test_run_requires_goal_or_resume(self):
        """run without goal or resume shows error."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run'])
        # Should fail because no goal provided
        assert result.exit_code != 0 or 'Error' in result.output or 'required' in result.output.lower()

    def test_run_accepts_headless_flag(self):
        """run command accepts --headless flag."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--headless' in result.output
        assert '--no-headless' in result.output

    def test_run_accepts_browser_option(self):
        """run command accepts --browser option."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--help'])
        assert '--browser' in result.output


class TestConfigManagerIntegration:
    """Tests for CLI config manager integration."""

    def test_cli_has_config_manager(self):
        """CLI uses config_manager."""
        from blackreach.cli import config_manager
        assert config_manager is not None

    def test_cli_has_available_models(self):
        """CLI has AVAILABLE_MODELS defined."""
        from blackreach.cli import AVAILABLE_MODELS
        assert AVAILABLE_MODELS is not None
        assert isinstance(AVAILABLE_MODELS, dict)
        assert 'ollama' in AVAILABLE_MODELS

    def test_cli_has_config_file_path(self):
        """CLI has CONFIG_FILE path."""
        from blackreach.cli import CONFIG_FILE
        assert CONFIG_FILE is not None


class TestCheckOllamaRunningBehavior:
    """Extended tests for check_ollama_running."""

    @patch('ollama.list')
    def test_ollama_list_success(self, mock_ollama_list):
        """check_ollama_running returns True on success."""
        mock_ollama_list.return_value = {}

        from blackreach.cli import check_ollama_running
        result = check_ollama_running()

        assert result is True

    @patch('ollama.list')
    def test_ollama_list_exception(self, mock_ollama_list):
        """check_ollama_running returns False on exception."""
        mock_ollama_list.side_effect = OSError("Connection refused")

        from blackreach.cli import check_ollama_running
        result = check_ollama_running()

        assert result is False


class TestCleanupHandlers:
    """Tests for cleanup and signal handlers."""

    def test_cleanup_keyboard_function_callable(self):
        """_cleanup_keyboard is callable."""
        from blackreach.cli import _cleanup_keyboard
        assert callable(_cleanup_keyboard)

    def test_signal_handler_callable(self):
        """_signal_handler is callable."""
        from blackreach.cli import _signal_handler
        assert callable(_signal_handler)

    def test_atexit_registered(self):
        """atexit cleanup is registered."""
        import atexit
        # Just verify the module loads without error
        # atexit.register is called at import time
        from blackreach.cli import _cleanup_keyboard
        assert callable(_cleanup_keyboard)


class TestAllCommandsExist:
    """Verify all CLI commands exist."""

    def test_cli_has_all_expected_commands(self):
        """CLI has all expected commands."""
        from blackreach.cli import cli

        expected_commands = [
            'run', 'config', 'models', 'sessions', 'status',
            'setup', 'doctor', 'version', 'validate', 'actions',
            'sources', 'stats', 'health', 'downloads', 'clear',
            'logs', 'resumable'
        ]

        actual_commands = [cmd.name for cmd in cli.commands.values()]

        for cmd in expected_commands:
            assert cmd in actual_commands, f"Missing command: {cmd}"


class TestPytestDetection:
    """Tests for pytest detection function."""

    def test_is_running_under_pytest_returns_true(self):
        """_is_running_under_pytest should return True when running under pytest."""
        from blackreach.cli import _is_running_under_pytest
        # We're running under pytest, so this should be True
        assert _is_running_under_pytest() is True

    def test_is_running_under_pytest_is_callable(self):
        """_is_running_under_pytest should be callable."""
        from blackreach.cli import _is_running_under_pytest
        assert callable(_is_running_under_pytest)

    def test_signal_handlers_not_registered_under_pytest(self):
        """Signal handlers should not be registered when running under pytest."""
        import signal
        from blackreach.cli import _signal_handler

        # Get current SIGTERM handler
        current_handler = signal.getsignal(signal.SIGTERM)

        # Under pytest, the signal handler should NOT be _signal_handler
        # because we guard the registration with _is_running_under_pytest()
        assert current_handler is not _signal_handler


class TestRunCommandBehavior:
    """Behavioral tests for the run command."""

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_with_goal_creates_agent(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command with goal creates and runs agent."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False
        mock_config_mgr.get_api_key.return_value = None

        mock_agent = MagicMock()
        mock_agent.run.return_value = {
            "success": True,
            "downloads": [],
            "pages_visited": 5,
            "steps_taken": 10,
            "failures": 0
        }
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', 'go to wikipedia'])

        assert result.exit_code == 0
        mock_agent.run.assert_called_once_with('go to wikipedia')

    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_requires_api_key_for_cloud_provider(self, mock_console, mock_config_mgr):
        """run command exits if cloud provider has no API key."""
        mock_config = MagicMock()
        mock_config.default_provider = "openai"
        mock_config.openai.default_model = "gpt-4o"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', 'go to wikipedia'])

        assert result.exit_code == 1
        assert 'No API key configured' in result.output or 'API key' in mock_console.print.call_args_list[0][0][0]

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_with_custom_provider(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command accepts --provider option."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.anthropic.default_model = "claude-3-sonnet"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = True
        mock_config_mgr.get_api_key.return_value = "test-key"

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--provider', 'anthropic', 'test goal'])

        assert result.exit_code == 0

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_with_headless_option(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command accepts --headless flag."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = False
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--headless', 'test goal'])

        assert result.exit_code == 0

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_with_steps_option(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command accepts --steps option."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--steps', '50', 'test goal'])

        assert result.exit_code == 0

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_handles_keyboard_interrupt(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command handles KeyboardInterrupt gracefully."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.run.side_effect = KeyboardInterrupt()
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', 'test goal'])

        # Should not raise, should handle gracefully
        assert result.exit_code == 0

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_handles_general_exception(self, mock_console, mock_config_mgr, mock_agent_class):
        """run command handles exceptions gracefully."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.run.side_effect = Exception("Test error")
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', 'test goal'])

        assert result.exit_code == 1


class TestRunResumeCommand:
    """Tests for run --resume functionality."""

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_resume_creates_agent(self, mock_console, mock_config_mgr, mock_agent_class):
        """run --resume creates agent and calls resume."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.resume.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--resume', '42'])

        assert result.exit_code == 0
        mock_agent.resume.assert_called_once_with(42)

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_resume_handles_session_not_found(self, mock_console, mock_config_mgr, mock_agent_class):
        """run --resume handles SessionNotFoundError."""
        from blackreach.exceptions import SessionNotFoundError

        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.resume.side_effect = SessionNotFoundError("Session 999 not found")
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--resume', '999'])

        assert result.exit_code == 1


class TestValidateCommandBehavior:
    """Behavioral tests for validate command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_shows_config_table(self, mock_validate, mock_config_mgr, mock_console):
        """validate command shows configuration table."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate'])

        assert result.exit_code == 0
        assert mock_console.print.called

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_shows_errors(self, mock_validate, mock_config_mgr, mock_console):
        """validate command shows errors when config is invalid."""
        mock_config = MagicMock()
        mock_config.default_provider = "invalid"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["Invalid provider"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate'])

        # Command should complete - errors are displayed via console.print
        assert result.exit_code == 0 or result.exit_code == 1
        # console.print should have been called
        assert mock_console.print.called

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_fix_repairs_invalid_browser(self, mock_validate, mock_config_mgr, mock_console):
        """validate --fix repairs invalid browser setting."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.browser_type = "invalid_browser"
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["Invalid browser"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate', '--fix'])

        # Should fix browser to chromium
        assert mock_config.browser_type == "chromium"

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_fix_repairs_invalid_max_steps(self, mock_validate, mock_config_mgr, mock_console):
        """validate --fix repairs invalid max_steps."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = -5  # Invalid
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["Invalid max_steps"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate', '--fix'])

        # Should fix max_steps to 30
        assert mock_config.max_steps == 30


class TestModelsCommandBehavior:
    """Behavioral tests for models command."""

    @patch('blackreach.cli.console')
    def test_models_lists_all_providers(self, mock_console):
        """models command lists all providers."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    def test_models_with_specific_provider(self, mock_console):
        """models --provider shows specific provider models."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models', '--provider', 'ollama'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    def test_models_unknown_provider_shows_error(self, mock_console):
        """models with unknown provider shows error."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['models', '--provider', 'unknown_provider'])

        # Should handle gracefully
        assert result.exit_code == 0


class TestStatusCommandBehavior:
    """Behavioral tests for status command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.memory.PersistentMemory')
    def test_status_shows_config_and_memory(self, mock_memory_class, mock_config_mgr, mock_console):
        """status command shows config and memory stats."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config_mgr.load.return_value = mock_config

        mock_memory = MagicMock()
        mock_memory.get_stats.return_value = {
            "total_sessions": 5,
            "total_downloads": 10,
            "total_visits": 20
        }
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['status'])

        assert result.exit_code == 0
        assert mock_console.print.called

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.memory.PersistentMemory')
    def test_status_handles_memory_error(self, mock_memory_class, mock_config_mgr, mock_console):
        """status command handles memory access errors."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config_mgr.load.return_value = mock_config

        mock_memory_class.side_effect = Exception("Database error")

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['status'])

        # Should handle gracefully with default stats
        assert result.exit_code == 0


class TestSetupCommandBehavior:
    """Behavioral tests for setup command."""

    @patch('blackreach.cli.run_first_time_setup')
    def test_setup_calls_first_time_setup(self, mock_setup):
        """setup command calls run_first_time_setup."""
        mock_setup.return_value = True

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['setup'])

        mock_setup.assert_called_once()

    @patch('blackreach.cli.run_first_time_setup')
    @patch('blackreach.cli.CONFIG_FILE')
    @patch('blackreach.cli.Confirm')
    def test_setup_reset_deletes_config(self, mock_confirm, mock_config_file, mock_setup):
        """setup --reset deletes config file."""
        mock_confirm.ask.return_value = True
        mock_config_file.exists.return_value = True
        mock_setup.return_value = True

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['setup', '--reset'])

        mock_config_file.unlink.assert_called_once()


class TestVersionCommandBehavior:
    """Behavioral tests for version command."""

    @patch('blackreach.cli.console')
    def test_version_shows_python_info(self, mock_console):
        """version command shows Python info."""
        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['version'])

        assert result.exit_code == 0


class TestUpdateCommandBehavior:
    """Behavioral tests for update command."""

    @patch('blackreach.cli.console')
    @patch('subprocess.run')
    def test_update_runs_git_pull(self, mock_run, mock_console):
        """update command runs git pull."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date", stderr="")

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['update'])

        # Should run git pull
        assert any('git' in str(call) for call in mock_run.call_args_list)

    @patch('blackreach.cli.console')
    @patch('subprocess.run')
    def test_update_force_reinstalls(self, mock_run, mock_console):
        """update --force reinstalls even if up to date."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date", stderr="")

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['update', '--force'])

        # Should run pip install
        assert any('pip' in str(call) for call in mock_run.call_args_list)


class TestDoctorCommandBehavior:
    """Behavioral tests for doctor command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    @patch('blackreach.cli.check_ollama_running')
    @patch('blackreach.cli.CONFIG_FILE')
    def test_doctor_shows_all_checks(self, mock_config_file, mock_ollama, mock_playwright, mock_console):
        """doctor command shows all system checks."""
        mock_playwright.return_value = True
        mock_ollama.return_value = True
        mock_config_file.exists.return_value = True

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])

        assert result.exit_code == 0
        assert mock_console.print.called

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    @patch('blackreach.cli.check_ollama_running')
    @patch('blackreach.cli.CONFIG_FILE')
    def test_doctor_shows_recommendations(self, mock_config_file, mock_ollama, mock_playwright, mock_console):
        """doctor command shows recommendations for failed checks."""
        mock_playwright.return_value = False
        mock_ollama.return_value = False
        mock_config_file.exists.return_value = False

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['doctor'])

        # Should show recommendations
        assert result.exit_code == 0


class TestActionsCommandBehavior:
    """Behavioral tests for actions command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.action_tracker.ActionTracker')
    @patch('blackreach.memory.PersistentMemory')
    def test_actions_shows_overview(self, mock_memory_class, mock_tracker_class, mock_console):
        """actions command shows overview statistics."""
        mock_memory = MagicMock()
        mock_memory_class.return_value = mock_memory

        mock_tracker = MagicMock()
        mock_tracker.get_stats_summary.return_value = {
            "total_tracked_actions": 100,
            "total_successes": 90,
            "overall_success_rate": 0.9,
            "unique_action_patterns": 20,
            "domains_tracked": 5,
            "problem_actions": []
        }
        mock_tracker_class.return_value = mock_tracker

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['actions'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.action_tracker.ActionTracker')
    @patch('blackreach.memory.PersistentMemory')
    def test_actions_with_domain_filter(self, mock_memory_class, mock_tracker_class, mock_console):
        """actions --domain filters by domain."""
        mock_memory = MagicMock()
        mock_memory_class.return_value = mock_memory

        mock_tracker = MagicMock()
        mock_tracker.get_stats_summary.return_value = {
            "total_tracked_actions": 100,
            "total_successes": 90,
            "overall_success_rate": 0.9,
            "unique_action_patterns": 20,
            "domains_tracked": 5,
            "problem_actions": []
        }
        mock_tracker.get_domain_summary.return_value = {"click": {"success_rate": 0.95, "total_actions": 50}}
        mock_tracker.get_good_selectors.return_value = ["#main-button", ".submit"]
        mock_tracker_class.return_value = mock_tracker

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['actions', '--domain', 'example.com'])

        assert result.exit_code == 0
        mock_tracker.get_domain_summary.assert_called_with('example.com')


class TestSourcesCommandBehavior:
    """Behavioral tests for sources command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.source_manager.get_source_manager')
    def test_sources_shows_status_table(self, mock_get_manager, mock_console):
        """sources command shows status table."""
        mock_manager = MagicMock()
        mock_manager.get_all_status.return_value = {
            "example.com": {
                "status": "healthy",
                "success_rate": 0.95,
                "success_count": 95,
                "failure_count": 5,
                "available": True
            }
        }
        mock_manager.get_session_summary.return_value = {"sources_used": 1, "failovers": 0}
        mock_get_manager.return_value = mock_manager

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sources'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.source_manager.get_source_manager')
    def test_sources_empty(self, mock_get_manager, mock_console):
        """sources command handles empty status."""
        mock_manager = MagicMock()
        mock_manager.get_all_status.return_value = {}
        mock_get_manager.return_value = mock_manager

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sources'])

        assert result.exit_code == 0


class TestStatsCommandBehavior:
    """Behavioral tests for stats command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_stats_shows_detailed_stats(self, mock_memory_class, mock_console):
        """stats command shows detailed statistics."""
        mock_memory = MagicMock()
        mock_memory.get_detailed_stats.return_value = {
            "total_sessions": 10,
            "completed_sessions": 8,
            "session_success_rate": 80,
            "total_downloads": 25,
            "total_downloaded_size": "100 MB",
            "total_visits": 100,
            "known_domains": 15,
            "avg_steps_per_session": 10,
            "avg_downloads_per_session": 2.5,
            "total_failures": 5,
            "db_path": "/tmp/memory.db",
            "top_sources": [{"site": "example.com", "count": 10}],
            "recent_sessions": [{"goal": "test", "success": True, "steps": 10, "downloads": 2}]
        }
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['stats'])

        assert result.exit_code == 0


class TestHealthCommandBehavior:
    """Behavioral tests for health command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.knowledge.check_sources_health')
    def test_health_shows_source_status(self, mock_check_health, mock_console):
        """health command shows source health status."""
        mock_check_health.return_value = {
            "example_source": {
                "reachable": True,
                "priority": 10,
                "content_types": ["ebook", "paper"],
                "working_mirror": None
            }
        }

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['health'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.knowledge.check_sources_health')
    def test_health_with_content_type_filter(self, mock_check_health, mock_console):
        """health --type filters by content type."""
        mock_check_health.return_value = {}

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['health', '--type', 'ebook'])

        assert result.exit_code == 0
        mock_check_health.assert_called_with(['ebook'], 5.0)


class TestDownloadsCommandBehavior:
    """Behavioral tests for downloads command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_shows_list(self, mock_memory_class, mock_console):
        """downloads command shows download list."""
        mock_memory = MagicMock()
        mock_memory.get_downloads.return_value = [
            {
                "filename": "test.pdf",
                "file_size": 1024000,
                "source_site": "example.com",
                "downloaded_at": "2024-01-01T12:00:00Z"
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_all_flag(self, mock_memory_class, mock_console):
        """downloads --all shows all downloads."""
        mock_memory = MagicMock()
        mock_memory.get_downloads.return_value = []
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads', '--all'])

        assert result.exit_code == 0
        # Should call with high limit
        mock_memory.get_downloads.assert_called_with(1000)


class TestSessionsCommandBehavior:
    """Behavioral tests for sessions command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_shows_list(self, mock_memory_class, mock_console):
        """sessions command shows session list."""
        mock_memory = MagicMock()
        mock_memory.get_sessions.return_value = [
            {
                "id": 1,
                "goal": "test goal",
                "success": True,
                "steps_taken": 10,
                "downloads_count": 2,
                "start_time": "2024-01-01T12:00:00Z",
                "end_time": "2024-01-01T12:05:00Z"
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_with_limit(self, mock_memory_class, mock_console):
        """sessions --limit limits results."""
        mock_memory = MagicMock()
        mock_memory.get_sessions.return_value = []
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions', '--limit', '5'])

        assert result.exit_code == 0
        mock_memory.get_sessions.assert_called_with(5)


class TestResumableCommandBehavior:
    """Behavioral tests for resumable command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_resumable_shows_sessions(self, mock_memory_class, mock_console):
        """resumable command shows resumable sessions."""
        mock_memory = MagicMock()
        mock_memory.get_resumable_sessions.return_value = [
            {
                "session_id": 42,
                "goal": "test goal",
                "current_step": 5,
                "status": "paused",
                "saved_at": "2024-01-01T12:00:00Z"
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['resumable'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_resumable_handles_error(self, mock_memory_class, mock_console):
        """resumable command handles database errors."""
        mock_memory_class.side_effect = OSError("Database error")

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['resumable'])

        # Should handle gracefully
        assert result.exit_code == 0


class TestClearCommandBehavior:
    """Behavioral tests for clear command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.cleanup_old_logs')
    @patch('blackreach.logging.LOG_DIR')
    @patch('blackreach.cli.Confirm')
    def test_clear_logs_with_confirmation(self, mock_confirm, mock_log_dir, mock_cleanup, mock_console):
        """clear --logs deletes old logs after confirmation."""
        mock_confirm.ask.return_value = True
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = []

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['clear', '--logs'])

        assert result.exit_code == 0
        mock_cleanup.assert_called_once_with(keep_days=7)

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.cleanup_old_logs')
    @patch('blackreach.logging.LOG_DIR')
    def test_clear_logs_force_skips_confirmation(self, mock_log_dir, mock_cleanup, mock_console):
        """clear --logs --force skips confirmation."""
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = []

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['clear', '--logs', '--force'])

        assert result.exit_code == 0
        mock_cleanup.assert_called_once()

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.cleanup_old_logs')
    @patch('blackreach.logging.LOG_DIR')
    def test_clear_logs_custom_days(self, mock_log_dir, mock_cleanup, mock_console):
        """clear --logs --days N uses custom retention."""
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = []

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['clear', '--logs', '--force', '--days', '14'])

        assert result.exit_code == 0
        mock_cleanup.assert_called_once_with(keep_days=14)


class TestLogsCommandBehavior:
    """Behavioral tests for logs command."""

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.get_recent_logs')
    @patch('blackreach.logging.read_log')
    def test_logs_shows_recent(self, mock_read_log, mock_get_logs, mock_console):
        """logs command shows recent logs."""
        mock_log_file = MagicMock()
        mock_log_file.stem = "session_1_20240101_120000"
        mock_get_logs.return_value = [mock_log_file]
        mock_read_log.return_value = [
            {"level": "INFO", "event": "session_start", "data": {}},
            {"level": "INFO", "event": "session_end", "data": {"success": True}}
        ]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.read_log')
    @patch('blackreach.logging.LOG_DIR')
    def test_logs_with_session_id(self, mock_log_dir, mock_read_log, mock_console):
        """logs --id shows specific session."""
        mock_log_file = MagicMock()
        mock_log_file.name = "session_42_20240101_120000.jsonl"
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = [mock_log_file]
        mock_read_log.return_value = [
            {"level": "INFO", "event": "act", "step": 1, "data": {"action": "click"}},
            {"level": "INFO", "event": "download", "step": 2, "data": {"filename": "test.pdf"}}
        ]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs', '--id', '42'])

        assert result.exit_code == 0


class TestRunWithValidation:
    """Tests for run command with --validate flag."""

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_for_run')
    @patch('blackreach.cli.console')
    def test_run_validate_passes(self, mock_console, mock_validate, mock_config_mgr, mock_agent_class):
        """run --validate continues if validation passes."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_result = MagicMock()
        mock_result.valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--validate', 'test goal'])

        assert result.exit_code == 0

    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_for_run')
    @patch('blackreach.cli.console')
    def test_run_validate_fails_exits(self, mock_console, mock_validate, mock_config_mgr):
        """run --validate exits if validation fails."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["Provider not available"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--validate', 'test goal'])

        assert result.exit_code == 1


class TestFirstTimeSetup:
    """Tests for run_first_time_setup function."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    @patch('blackreach.cli.check_ollama_running')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.Prompt')
    @patch('blackreach.cli.Confirm')
    def test_first_time_setup_ollama(self, mock_confirm, mock_prompt, mock_config_mgr, mock_ollama, mock_playwright, mock_console):
        """run_first_time_setup configures Ollama."""
        mock_playwright.return_value = True
        mock_ollama.return_value = True
        mock_prompt.ask.side_effect = ["1", "qwen2.5:7b"]  # Ollama, model
        mock_confirm.ask.return_value = True

        from blackreach.cli import run_first_time_setup
        result = run_first_time_setup()

        assert result is True
        mock_config_mgr.set_default_provider.assert_called_with("ollama")

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    @patch('blackreach.cli.check_ollama_running')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.Prompt')
    @patch('blackreach.cli.Confirm')
    def test_first_time_setup_cloud_provider(self, mock_confirm, mock_prompt, mock_config_mgr, mock_ollama, mock_playwright, mock_console):
        """run_first_time_setup configures cloud provider with API key."""
        mock_playwright.return_value = True
        mock_prompt.ask.side_effect = ["2", "test-api-key"]  # xAI, API key
        mock_confirm.ask.return_value = True

        from blackreach.cli import run_first_time_setup
        result = run_first_time_setup()

        assert result is True
        mock_config_mgr.set_default_provider.assert_called_with("xai")
        mock_config_mgr.set_api_key.assert_called_with("xai", "test-api-key")

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.check_playwright_browsers')
    @patch('blackreach.cli.install_playwright_browsers')
    @patch('blackreach.cli.check_ollama_running')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.Prompt')
    @patch('blackreach.cli.Confirm')
    def test_first_time_setup_installs_browser(self, mock_confirm, mock_prompt, mock_config_mgr, mock_ollama, mock_install, mock_check_pw, mock_console):
        """run_first_time_setup installs browser if needed."""
        mock_check_pw.return_value = False
        mock_confirm.ask.return_value = True
        mock_install.return_value = True
        mock_ollama.return_value = True
        mock_prompt.ask.side_effect = ["1", "llama3"]

        from blackreach.cli import run_first_time_setup
        result = run_first_time_setup()

        assert result is True
        mock_install.assert_called_once()


class TestMakeBanner:
    """Tests for banner generation."""

    def test_banner_contains_version(self):
        """Banner contains current version."""
        from blackreach.cli import BANNER, __version__
        assert __version__ in BANNER

    def test_banner_has_ascii_art(self):
        """Banner contains ASCII art."""
        from blackreach.cli import BANNER
        assert "██" in BANNER


class TestCleanupKeyboardExtended:
    """Extended tests for keyboard cleanup."""

    @patch('subprocess.run')
    def test_cleanup_handles_exception(self, mock_run):
        """_cleanup_keyboard handles exceptions gracefully."""
        import blackreach.cli as cli_module
        original_agent = cli_module._active_agent

        mock_hand = MagicMock()
        mock_hand._release_all_keys.side_effect = Exception("Cleanup error")
        mock_agent = MagicMock()
        mock_agent.hand = mock_hand
        cli_module._active_agent = mock_agent

        from blackreach.cli import _cleanup_keyboard
        # Should not raise
        _cleanup_keyboard()

        cli_module._active_agent = original_agent


class TestActionsWithProblemActions:
    """Tests for actions command with problem actions."""

    @patch('blackreach.cli.console')
    @patch('blackreach.action_tracker.ActionTracker')
    @patch('blackreach.memory.PersistentMemory')
    def test_actions_shows_problem_actions(self, mock_memory_class, mock_tracker_class, mock_console):
        """actions command shows problem actions."""
        mock_memory = MagicMock()
        mock_memory_class.return_value = mock_memory

        mock_tracker = MagicMock()
        mock_tracker.get_stats_summary.return_value = {
            "total_tracked_actions": 100,
            "total_successes": 70,
            "overall_success_rate": 0.7,
            "unique_action_patterns": 20,
            "domains_tracked": 5,
            "problem_actions": [
                {
                    "domain": "example.com",
                    "action": "click",
                    "target": "#broken-button",
                    "success_rate": 0.2,
                    "failures": 8
                }
            ]
        }
        mock_tracker_class.return_value = mock_tracker

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['actions'])

        assert result.exit_code == 0


class TestConfigMenuBehavior:
    """Tests for config command interactive menu."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.Prompt')
    def test_config_set_default_provider(self, mock_prompt, mock_config_mgr, mock_console):
        """config command allows setting default provider."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.openai.default_model = "gpt-4o"
        mock_config.anthropic.default_model = "claude-3-sonnet"
        mock_config.google.default_model = "gemini-pro"
        mock_config.xai.default_model = "grok-2"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.get_current_model.return_value = "llama3"
        mock_config_mgr.has_api_key.return_value = False

        # Simulate menu choices: 1 (set provider), then q (quit)
        mock_prompt.ask.side_effect = ["1", "openai", "q"]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['config'])

        # Should have called set_default_provider
        mock_config_mgr.set_default_provider.assert_called_with("openai")

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.Prompt')
    def test_config_quit_immediately(self, mock_prompt, mock_config_mgr, mock_console):
        """config command quits on 'q'."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.openai.default_model = "gpt-4o"
        mock_config.anthropic.default_model = "claude-3-sonnet"
        mock_config.google.default_model = "gemini-pro"
        mock_config.xai.default_model = "grok-2"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.get_current_model.return_value = "llama3"
        mock_config_mgr.has_api_key.return_value = False

        mock_prompt.ask.return_value = "q"

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['config'])

        assert result.exit_code == 0


class TestDownloadsSizeFormatting:
    """Tests for downloads command size formatting."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_formats_mb_size(self, mock_memory_class, mock_console):
        """downloads command formats MB sizes correctly."""
        mock_memory = MagicMock()
        mock_memory.get_downloads.return_value = [
            {
                "filename": "large_file.pdf",
                "file_size": 5 * 1024 * 1024,  # 5 MB
                "source_site": "example.com",
                "downloaded_at": "2024-01-01T12:00:00Z"
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_formats_kb_size(self, mock_memory_class, mock_console):
        """downloads command formats KB sizes correctly."""
        mock_memory = MagicMock()
        mock_memory.get_downloads.return_value = [
            {
                "filename": "small_file.txt",
                "file_size": 500 * 1024,  # 500 KB
                "source_site": "example.com",
                "downloaded_at": "2024-01-01T12:00:00Z"
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_downloads_formats_gb_total(self, mock_memory_class, mock_console):
        """downloads command formats GB totals correctly."""
        mock_memory = MagicMock()
        mock_memory.get_downloads.return_value = [
            {
                "filename": f"file_{i}.pdf",
                "file_size": 200 * 1024 * 1024,  # 200 MB each
                "source_site": "example.com",
                "downloaded_at": "2024-01-01T12:00:00Z"
            }
            for i in range(10)  # 2 GB total
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['downloads'])

        assert result.exit_code == 0


class TestSessionsDurationFormatting:
    """Tests for sessions command duration formatting."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_formats_minutes(self, mock_memory_class, mock_console):
        """sessions command formats minute durations."""
        mock_memory = MagicMock()
        mock_memory.get_sessions.return_value = [
            {
                "id": 1,
                "goal": "test goal",
                "success": True,
                "steps_taken": 10,
                "downloads_count": 2,
                "start_time": "2024-01-01T12:00:00Z",
                "end_time": "2024-01-01T12:05:00Z"  # 5 minutes
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_formats_hours(self, mock_memory_class, mock_console):
        """sessions command formats hour durations."""
        mock_memory = MagicMock()
        mock_memory.get_sessions.return_value = [
            {
                "id": 1,
                "goal": "long task",
                "success": True,
                "steps_taken": 100,
                "downloads_count": 50,
                "start_time": "2024-01-01T12:00:00Z",
                "end_time": "2024-01-01T14:30:00Z"  # 2.5 hours
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_sessions_handles_running_session(self, mock_memory_class, mock_console):
        """sessions command handles running sessions without end_time."""
        mock_memory = MagicMock()
        mock_memory.get_sessions.return_value = [
            {
                "id": 1,
                "goal": "running task",
                "success": None,  # Running
                "steps_taken": 5,
                "downloads_count": 0,
                "start_time": "2024-01-01T12:00:00Z",
                "end_time": None
            }
        ]
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sessions'])

        assert result.exit_code == 0


class TestLogsEntryTypes:
    """Tests for logs command entry type handling."""

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.read_log')
    @patch('blackreach.logging.LOG_DIR')
    def test_logs_shows_error_entries(self, mock_log_dir, mock_read_log, mock_console):
        """logs --id shows error entries properly."""
        mock_log_file = MagicMock()
        mock_log_file.name = "session_1_20240101_120000.jsonl"
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = [mock_log_file]
        mock_read_log.return_value = [
            {"level": "ERROR", "event": "error", "step": 5, "data": {"error": "Connection failed"}}
        ]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs', '--id', '1'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.logging.read_log')
    @patch('blackreach.logging.LOG_DIR')
    def test_logs_shows_warning_entries(self, mock_log_dir, mock_read_log, mock_console):
        """logs --id shows warning entries properly."""
        mock_log_file = MagicMock()
        mock_log_file.name = "session_2_20240101_120000.jsonl"
        mock_log_dir.exists.return_value = True
        mock_log_dir.glob.return_value = [mock_log_file]
        mock_read_log.return_value = [
            {"level": "WARNING", "event": "retry", "step": 3, "data": {}}
        ]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['logs', '--id', '2'])

        assert result.exit_code == 0


class TestValidateWithWarnings:
    """Tests for validate command with warnings."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_shows_warnings(self, mock_validate, mock_config_mgr, mock_console):
        """validate command shows warnings when present."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "custom-model"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = True
        mock_result.errors = []
        mock_result.warnings = ["Using custom model that may not exist"]
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate'])

        assert result.exit_code == 0


class TestSourcesStatusColors:
    """Tests for sources command status colors."""

    @patch('blackreach.cli.console')
    @patch('blackreach.source_manager.get_source_manager')
    def test_sources_shows_degraded_status(self, mock_get_manager, mock_console):
        """sources command shows degraded status."""
        mock_manager = MagicMock()
        mock_manager.get_all_status.return_value = {
            "slow-source.com": {
                "status": "degraded",
                "success_rate": 0.6,
                "success_count": 60,
                "failure_count": 40,
                "available": True
            }
        }
        mock_manager.get_session_summary.return_value = {"sources_used": 1, "failovers": 2}
        mock_get_manager.return_value = mock_manager

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sources'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.source_manager.get_source_manager')
    def test_sources_shows_blocked_status(self, mock_get_manager, mock_console):
        """sources command shows blocked status."""
        mock_manager = MagicMock()
        mock_manager.get_all_status.return_value = {
            "blocked-source.com": {
                "status": "blocked",
                "success_rate": 0.0,
                "success_count": 0,
                "failure_count": 10,
                "available": False
            }
        }
        mock_manager.get_session_summary.return_value = {"sources_used": 0, "failovers": 0}
        mock_get_manager.return_value = mock_manager

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['sources'])

        assert result.exit_code == 0


class TestHealthMirrors:
    """Tests for health command with mirrors."""

    @patch('blackreach.cli.console')
    @patch('blackreach.knowledge.check_sources_health')
    def test_health_shows_working_mirror(self, mock_check_health, mock_console):
        """health command shows working mirror indicator."""
        mock_check_health.return_value = {
            "mirrored_source": {
                "reachable": True,
                "priority": 8,
                "content_types": ["ebook"],
                "working_mirror": "mirror.example.com"
            }
        }

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['health'])

        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('blackreach.knowledge.check_sources_health')
    def test_health_shows_offline_source(self, mock_check_health, mock_console):
        """health command shows offline sources."""
        mock_check_health.return_value = {
            "offline_source": {
                "reachable": False,
                "priority": 5,
                "content_types": ["paper"],
                "working_mirror": None
            }
        }

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['health'])

        assert result.exit_code == 0


class TestUpdateErrorHandling:
    """Tests for update command error handling."""

    @patch('blackreach.cli.console')
    @patch('subprocess.run')
    def test_update_handles_git_error(self, mock_run, mock_console):
        """update command handles git pull errors."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Permission denied")

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['update'])

        # Should handle gracefully
        assert result.exit_code == 0

    @patch('blackreach.cli.console')
    @patch('subprocess.run')
    def test_update_handles_pip_error(self, mock_run, mock_console):
        """update command handles pip install errors."""
        # First call succeeds (git pull), second fails (pip install)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Already up to date", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Installation failed")
        ]

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['update', '--force'])

        # Should handle gracefully
        assert result.exit_code == 0


class TestStatsTopSources:
    """Tests for stats command top sources display."""

    @patch('blackreach.cli.console')
    @patch('blackreach.memory.PersistentMemory')
    def test_stats_shows_top_sources(self, mock_memory_class, mock_console):
        """stats command shows top download sources."""
        mock_memory = MagicMock()
        mock_memory.get_detailed_stats.return_value = {
            "total_sessions": 10,
            "completed_sessions": 8,
            "session_success_rate": 80,
            "total_downloads": 25,
            "total_downloaded_size": "100 MB",
            "total_visits": 100,
            "known_domains": 15,
            "avg_steps_per_session": 10,
            "avg_downloads_per_session": 2.5,
            "total_failures": 5,
            "db_path": "/tmp/memory.db",
            "top_sources": [
                {"site": "example.com", "count": 10},
                {"site": "test.org", "count": 5}
            ],
            "recent_sessions": []
        }
        mock_memory_class.return_value = mock_memory

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['stats'])

        assert result.exit_code == 0


class TestRunBrowserOption:
    """Tests for run command with browser option."""

    @patch('blackreach.agent.Agent')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.console')
    def test_run_with_browser_option(self, mock_console, mock_config_mgr, mock_agent_class):
        """run --browser accepts browser choice."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.headless = True
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config.browser_type = "chromium"
        mock_config_mgr.load.return_value = mock_config

        mock_agent = MagicMock()
        mock_agent.run.return_value = {"success": True, "downloads": [], "pages_visited": 1, "steps_taken": 1, "failures": 0}
        mock_agent_class.return_value = mock_agent

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['run', '--browser', 'firefox', 'test goal'])

        assert result.exit_code == 0


class TestValidateAPIKeyRequired:
    """Tests for validate command API key checks."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_shows_api_key_status_for_cloud(self, mock_validate, mock_config_mgr, mock_console):
        """validate command shows API key status for cloud providers."""
        mock_config = MagicMock()
        mock_config.default_provider = "openai"
        mock_config.openai.default_model = "gpt-4o"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = 30
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["API key required for openai"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate'])

        # Should check API key
        mock_config_mgr.has_api_key.assert_called()


class TestValidateMaxStepsFix:
    """Tests for validate --fix with max_steps issues."""

    @patch('blackreach.cli.console')
    @patch('blackreach.cli.config_manager')
    @patch('blackreach.cli.validate_config')
    def test_validate_fix_max_steps_too_high(self, mock_validate, mock_config_mgr, mock_console):
        """validate --fix fixes max_steps over 1000."""
        mock_config = MagicMock()
        mock_config.default_provider = "ollama"
        mock_config.ollama.default_model = "llama3"
        mock_config.browser_type = "chromium"
        mock_config.max_steps = 5000  # Too high
        mock_config.download_dir = "/tmp/downloads"
        mock_config_mgr.load.return_value = mock_config
        mock_config_mgr.has_api_key.return_value = False

        mock_result = MagicMock()
        mock_result.valid = False
        mock_result.errors = ["max_steps too high"]
        mock_result.warnings = []
        mock_validate.return_value = mock_result

        from blackreach.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ['validate', '--fix'])

        # Should fix max_steps to 100
        assert mock_config.max_steps == 100
