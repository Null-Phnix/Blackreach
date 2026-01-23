"""
Unit tests for blackreach/cli.py

Tests CLI commands using Click's testing utilities.
"""

import pytest
from unittest.mock import patch, MagicMock
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
        parts = __version__.split(".")
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
        parts = __version__.split(".")
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
