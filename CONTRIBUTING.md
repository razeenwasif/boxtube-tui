# Contributing to BoxTube

Thanks for your interest in improving BoxTube. This document covers how to set up
your environment, the conventions we follow, and how to submit changes. For a
deeper tour of the codebase, see the [development guide](docs/development.md).

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report bugs** — open an issue with steps to reproduce, your terminal and OS,
  and the output of `mpv --version` and `.venv/bin/yt-dlp --version`.
- **Suggest features** — open an issue describing the use case.
- **Submit fixes or features** — open a pull request following the guidelines
  below.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # runtime deps + test tooling
```

Run the app locally:

```bash
make run            # or: .venv/bin/python -m boxtube
```

Run the test suite:

```bash
make test           # or: .venv/bin/python -m pytest
```

See the [Makefile](Makefile) for all available tasks (`make help`).

## Pull request guidelines

1. **Branch** from the default branch; keep each PR focused on a single concern.
2. **Tests** — add or update tests for behavior changes. The suite must pass.
3. **Style** — match the surrounding code (see below). Keep functions small and
   readable.
4. **Docs** — update the relevant file in `docs/` and the `README.md` when you
   change user-facing behavior.
5. **Changelog** — add an entry under `## [Unreleased]` in
   [`CHANGELOG.md`](CHANGELOG.md).
6. **Commits** — write clear, imperative commit messages (e.g.
   "Add sixel detection for foot terminal").

## Coding standards

- **Python**: target 3.10+, use `from __future__ import annotations`, and type
  hints on public functions.
- **Docstrings**: module- and function-level docstrings explaining *why*, not
  just *what*. Comments should capture non-obvious decisions.
- **Threading**: long-running work (network, subprocess) runs in Textual workers
  (`@work(thread=True)`). Never touch widgets from a worker thread — marshal back
  to the UI thread with `self.call_from_thread(...)`. See
  [architecture](docs/architecture.md#threading-model).
- **Styling**: keep colors and layout in `boxtube/boxtube.tcss`, not inline.
- **Line length**: ~100 columns.

## Reporting security issues

Do **not** open public issues for security vulnerabilities. Follow the process in
[SECURITY.md](SECURITY.md).
