"""Terminal regressions: truthful outcomes, safe rendering, and install checks."""
import io
import json
import signal
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console


def render_result(monkeypatch, result, interactive=False):
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=False, width=100)
    if interactive:
        import blackreach.ui as ui
        monkeypatch.setattr(ui, "console", console)
        ui.AgentProgress().complete(result["success"], result)
    else:
        import blackreach.cli as cli
        monkeypatch.setattr(cli, "console", console)
        cli._show_results(result)
    return stream.getvalue()


@pytest.mark.parametrize("interactive", [False, True])
def test_terminal_explains_permanent_failure(monkeypatch, interactive):
    result = {"success": False, "status": "error", "stop_reason": "permanent_error",
              "error": "Model unavailable for this API account", "steps_taken": 1,
              "actions_taken": 0, "session_id": 7, "resumable": False}
    text = render_result(monkeypatch, result, interactive)
    assert "Model unavailable for this API account" in text
    assert "1" in text
    assert "Incomplete" not in text
    assert "--resume" not in text


def test_success_without_browser_action_is_not_incomplete(monkeypatch):
    text = render_result(monkeypatch, {"success": True, "steps_taken": 0,
                         "result": "Already satisfied [red]literal[/red]"}, True)
    assert "Success" in text
    assert "[red]literal[/red]" in text


@pytest.mark.parametrize("interactive", [False, True])
def test_resume_hint_requires_saved_state(monkeypatch, interactive):
    result = {"success": False, "status": "interrupted", "stop_reason": "interrupted",
              "paused": True, "session_id": 42, "resumable": True}
    assert "blackreach run --resume 42" in render_result(monkeypatch, result, interactive)
    result["resumable"] = False
    assert "--resume" not in render_result(monkeypatch, result, interactive)


def test_browser_dry_run_success_does_not_prove_binary_installed(tmp_path):
    from blackreach.cli import check_playwright_browsers
    with patch("playwright.sync_api.sync_playwright") as factory:
        factory.return_value.__enter__.return_value.chromium.executable_path = str(tmp_path / "missing")
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            assert check_playwright_browsers() is False


def test_browser_check_accepts_only_executable_file(tmp_path):
    from blackreach.cli import check_playwright_browsers
    binary = tmp_path / "chromium"
    binary.write_text("#!/bin/sh\n")
    with patch("playwright.sync_api.sync_playwright") as factory:
        factory.return_value.__enter__.return_value.chromium.executable_path = str(binary)
        binary.chmod(0o644)
        assert check_playwright_browsers() is False
        binary.chmod(0o755)
        assert check_playwright_browsers() is True


def test_sigint_enters_agent_checkpoint_path():
    from blackreach.cli import _signal_handler
    with patch("blackreach.cli._cleanup_keyboard"), pytest.raises(KeyboardInterrupt):
        _signal_handler(signal.SIGINT, None)


@pytest.mark.parametrize(('status', 'exit_code'), [('success', 0), ('max_steps', 2), ('error', 1), ('interrupted', 130)])
def test_json_cli_result_and_exit_code(monkeypatch, status, exit_code):
    from click.testing import CliRunner

    from blackreach.cli import cli
    from blackreach.config import Config
    cfg = Config()
    cfg.ollama.base_url = 'http://127.0.0.1:11434'
    cfg.ollama.max_tokens = 8192
    cfg.ollama.timeout_seconds = 25
    cfg.browser_type = 'firefox'
    result = {'success': status == 'success', 'status': status,
              'stop_reason': status, 'steps_taken': 1, 'actions_taken': 0}
    with patch('blackreach.cli.config_manager') as manager, patch('blackreach.agent.Agent') as agent:
        manager.load.return_value = cfg
        agent.return_value.run.return_value = result
        response = CliRunner().invoke(cli, ['run', '--json', 'local fixture'])
        assert response.exit_code == exit_code
        assert json.loads(response.output) == result
        agent.return_value.run.assert_called_once_with('local fixture', quiet=True)
        options = agent.call_args.kwargs
        assert options['llm_config'].api_base == cfg.ollama.base_url
        assert options['llm_config'].max_tokens == 8192
        assert options['llm_config'].timeout_seconds == 25
        assert options['agent_config'].browser_type == 'firefox'
        manager.get_api_key.assert_not_called()


def test_resume_passes_explicit_total_budget():
    from click.testing import CliRunner

    from blackreach.cli import cli
    from blackreach.config import Config
    with patch('blackreach.cli.config_manager') as manager, patch('blackreach.agent.Agent') as agent:
        manager.load.return_value = Config()
        agent.return_value.resume.return_value = {'success': True, 'status': 'success'}
        response = CliRunner().invoke(cli, ['run', '--json', '--resume', '7', '--steps', '60'])
        assert response.exit_code == 0
        agent.return_value.resume.assert_called_once_with(7, quiet=True, max_steps=60)


def test_doctor_offline_avoids_provider_requests():
    from click.testing import CliRunner

    from blackreach.cli import cli
    from blackreach.config import Config
    with patch('blackreach.cli.config_manager') as manager, patch('blackreach.cli.check_ollama_running') as ollama:
        manager.load.return_value = Config()
        response = CliRunner().invoke(cli, ['doctor', '--offline', '--json'])
        assert response.exit_code == 0
        assert json.loads(response.output)['provider_access_tested'] is False
        ollama.assert_not_called()
        manager.get_api_key.assert_not_called()
