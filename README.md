# Blackreach

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-7c3aed?style=flat-square&labelColor=07061a)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee?style=flat-square&labelColor=07061a)](LICENSE)
[![Version](https://img.shields.io/badge/version-v5.0.0--beta.2-9f6ff3?style=flat-square&labelColor=07061a)](https://github.com/Null-Phnix/Blackreach/releases)
[![Tests](https://img.shields.io/badge/tests-3%2C055_passing-4ade80?style=flat-square&labelColor=07061a)](tests/)

**A local-first browser and research agent that preserves progress and verifies
outcomes.**

[Watch the 27-second proof film](https://phnix.dev/projects/blackreach.html)
· [Read the engineering case study](https://phnix.dev/posts/how-blackreach-works.html)
· [Inspect the source](https://github.com/Null-Phnix/Blackreach)

## Why Blackreach exists

A browser action is not the same thing as a completed task. Real web work can
span several steps, encounter noisy pages, lose a session, or finish on the
wrong result.

Blackreach is designed around four practical requirements:

- reduce complex pages into focused observations;
- preserve enough state to resume interrupted work;
- check outcomes separately from an agent's completion report;
- keep uncertain or incomplete results visible.

## Public proof

The public repository includes unit, integration, browser, recovery, and
contract tests. The exact public commit used for the case study,
[`8a6a8c7`](https://github.com/Null-Phnix/Blackreach/commit/8a6a8c7bdae44a8bd52f13dd3de17556ce2704bd),
completed the full 3,055-test suite.

The controlled demo uses Blackreach's public browser code against Wikipedia. It
searches for Browser automation, follows the observed Selenium link, and checks
the visible destination heading separately.

| Evidence | Result |
|---|---|
| Source | Exact public commit linked above |
| Suite | 3,055 tests passed |
| Browser | Real Chromium session on a public website |
| Outcome | Visible `Selenium (software)` heading verified |
| Limit | Deterministic product proof, not a model-planning benchmark |

The film labels its scripted decision path directly. It demonstrates the
browser control and verification surface without claiming unrestricted
autonomy or open-web reliability.

## Inspect it locally

Blackreach is currently distributed from source rather than PyPI:

```bash
git clone https://github.com/Null-Phnix/Blackreach.git
cd Blackreach
python -m venv .venv
source .venv/bin/activate
python -m pip install uv==0.10.4
uv sync --locked --extra dev --extra server
uv run playwright install chromium
```

Start with the public command surface:

```bash
uv run blackreach --help
uv run blackreach setup
uv run blackreach doctor
```

Run the test suite:

```bash
uv run pytest tests/
```

## Public boundary

The public case study intentionally stops at the product surface, testing
discipline, and independently visible outcome. Current private deployment
topology, credentials, live session material, and operational runbooks are not
part of that public evidence.

## Contributing

Bug reports and focused pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a change.

## License

MIT. See [LICENSE](LICENSE).
