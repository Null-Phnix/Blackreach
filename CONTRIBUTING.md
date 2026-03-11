# Contributing to Blackreach

Thank you for your interest in contributing to Blackreach! This document explains how to get started, how to run the tests, and how to submit changes.

---

## Setting Up the Development Environment

1. **Clone the repository**

   ```bash
   git clone https://github.com/phnix/blackreach
   cd blackreach
   ```

2. **Install in editable mode with dev dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

3. **Install the Playwright browser**

   ```bash
   playwright install chromium
   ```

4. **Verify the installation**

   ```bash
   blackreach --version
   pytest tests/ -q --tb=short -x --ignore=tests/test_integration.py --ignore=tests/test_agent_e2e.py
   ```

---

## Running Tests

Run the full unit test suite:

```bash
pytest tests/ -q --tb=short
```

Run with coverage:

```bash
pytest tests/ --cov=blackreach --cov-report=term-missing -q
```

Skip slow integration tests (which require a live browser):

```bash
pytest tests/ -q --ignore=tests/test_integration.py \
    --ignore=tests/test_agent_e2e.py \
    --ignore=tests/test_integration_browser.py \
    --ignore=tests/test_integration_agent.py
```

Run a single test file:

```bash
pytest tests/test_browser.py -v
```

---

## Code Style

Blackreach uses **black** for formatting and **ruff** for linting.

Format code:

```bash
black blackreach/ tests/
```

Lint code:

```bash
ruff check blackreach/ tests/
```

Both tools are included in the `[dev]` extras and are checked in CI. Please run them before submitting a PR.

---

## Submitting a Pull Request

1. Fork the repository and create a branch from `main`.
2. Make your changes. Write or update tests for any code you add or modify.
3. Ensure all tests pass: `pytest tests/ -q --tb=short`.
4. Ensure code is formatted: `black blackreach/ tests/` and `ruff check blackreach/`.
5. Open a pull request against `main` and fill out the PR template.

Keep pull requests focused on a single concern. If you have multiple unrelated improvements, open separate PRs.

---

## Reporting Bugs

Please use the [GitHub Issues](https://github.com/phnix/blackreach/issues) tracker. Before opening a new issue, search to see if it has already been reported.

When filing a bug report, use the **Bug Report** issue template and include:

- A clear description of what went wrong
- Steps to reproduce
- Expected vs actual behavior
- Your OS, Python version, and LLM provider
- Any relevant log output (use `blackreach run --verbose` to capture logs)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this standard. Please report unacceptable behavior to the project maintainers via GitHub Issues.
