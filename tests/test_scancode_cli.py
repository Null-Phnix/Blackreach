"""Tests for blackreach CLI scancode command."""

from click.testing import CliRunner
import pytest

from blackreach.cli import cli


class TestScancodeCLI:

    def test_scancode_basic(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['scancode', 'https://wikipedia.org/wiki/Python'])
        assert result.exit_code == 0
        assert 'LIGHTWEIGHT' in result.output

    def test_scancode_verbose(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['scancode', 'https://wikipedia.org/wiki/Python', '--verbose'])
        assert result.exit_code == 0
        assert 'LIGHTWEIGHT' in result.output
        assert 'Analysis Details' in result.output

    def test_scancode_hard_site(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['scancode', 'https://linkedin.com/login'])
        assert result.exit_code == 0
        assert 'FULL_STEALTH' in result.output or 'HEADLESS' in result.output

    def test_scancode_refresh(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['scancode', 'https://wikipedia.org', '--refresh'])
        assert result.exit_code == 0
        assert 'LIGHTWEIGHT' in result.output
