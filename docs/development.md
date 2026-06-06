# Development guide

How to set up a development environment, navigate the code, run tests, and cut a
release. For contribution process and standards, see
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # runtime deps + pytest
```

Or with the [Makefile](../Makefile):

```bash
make dev        # editable install with dev extras
make help       # list all tasks
```

## Project structure

```
boxtube/
├── app.py          # Textual App: layout, events, orchestration
├── youtube.py      # search (yt-dlp), Video model, find_ytdlp, formatting
├── thumbnails.py   # thumbnail download + in-memory cache (PIL)
├── player.py       # mpv command construction + video-output detection
├── boxtube.tcss    # theme/layout (Textual CSS)
└── __main__.py     # module entry point

docs/               # this documentation
tests/              # pytest suite
```

See [architecture.md](architecture.md) for how these fit together, the data-flow
diagrams, and the threading model.

## Running locally

```bash
make run                      # .venv/bin/python -m boxtube
BOXTUBE_VO=tct make run       # force a video output while testing
```

Textual ships a devtools console that's invaluable for debugging layout and
messages:

```bash
.venv/bin/textual console     # in one terminal
.venv/bin/textual run --dev boxtube.app:BoxTube   # in another
```

## Testing

The suite uses `pytest` and Textual's headless `App.run_test()` harness. It avoids
the network where practical (search/thumbnail fetching are monkeypatched), so most
tests run offline and fast.

```bash
make test                     # all tests
.venv/bin/python -m pytest tests/test_player.py -v   # one file
.venv/bin/python -m pytest -k detect_vo              # by keyword
```

What's covered:

| File | Focus |
|------|-------|
| `tests/test_youtube.py` | Formatting helpers, `Video` properties, `find_ytdlp`, search JSON parsing (mocked subprocess) |
| `tests/test_player.py` | `detect_vo` across terminals, `build_command` structure |
| `tests/test_app.py` | Headless UI: boot, populate, highlight navigation, details rendering, thumbnail stale-guard |

A handful of tests are marked `@pytest.mark.network` and hit YouTube; they're for
manual verification and can be deselected:

```bash
.venv/bin/python -m pytest -m "not network"
```

### Writing tests

- Use `async with app.run_test() as pilot:` for UI behavior; drive it with
  `await pilot.press(...)` and `await pilot.pause()`.
- Monkeypatch `boxtube.youtube.search` and `boxtube.thumbnails.fetch` to keep
  tests offline and deterministic.
- Reach widgets with `app.query_one("#id", WidgetType)`. (Note: an empty
  container is falsy via `__len__` — assert on attributes, not truthiness.)

## Coding standards

- Python 3.10+, `from __future__ import annotations`, type hints on public APIs.
- Keep blocking work (network, subprocess) in `@work(thread=True)` workers and
  marshal UI updates with `call_from_thread`. Never mutate widgets off the UI
  thread.
- Keep presentation in `boxtube.tcss`; keep colors out of Python where possible.
- Comment the *why* behind non-obvious choices; match the surrounding style.

## Dependencies

Runtime and dev dependencies are declared in [`pyproject.toml`](../pyproject.toml).
`requirements.txt` mirrors the runtime set for convenience. When you change one,
update the other.

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
```

## Releasing

1. Update `version` in `pyproject.toml` and `boxtube/__init__.py`.
2. Move `## [Unreleased]` notes into a new dated version section in
   [`CHANGELOG.md`](../CHANGELOG.md).
3. Run `make test`.
4. Tag the release: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push --tags`.

Versioning follows [SemVer](https://semver.org/): patch for fixes, minor for
backward-compatible features, major for breaking changes.
