# BoxTube

> A fast, modern, keyboard-driven terminal client for searching and watching
> YouTube — without ever leaving your terminal.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Built with Textual](https://img.shields.io/badge/built%20with-Textual-ff6b6b)](https://textual.textualize.io/)

BoxTube is a TUI (terminal user interface) YouTube client with a YouTube-like
layout. Search YouTube, **sign in to browse your subscriptions feed, history,
liked videos, watch later, and playlists**, see **inline thumbnail previews**, and
**watch videos rendered directly inside the terminal** via [mpv](https://mpv.io/) —
using your terminal's native graphics protocol when available. No API key required.

```
●  BoxTube                                               ● Signed in
╭─ Search ──────────────────────────────────────────────────────────────╮
│ lofi hip hop                                                           │
╰───────────────────────────────────────────────────────────────────────╯
╭─ Library ──╮╭─ Home — Subscriptions (3) ──╮╭─ Preview ────────────────╮
│▌🏠 Home    ││▌Never Gonna Give You Up     ││      ░▒▓ thumbnail ▓▒░   │
│ 🕘 History ││ Rick Astley   3:33  1.6B    ││                          │
│ 👍 Liked   ││ lofi hip hop radio          ││ Never Gonna Give You Up  │
│ ⏰ Later   ││ Lofi Girl   —  55.2M        ││ Channel  Rick Astley     │
│ 🎵 Playlist││ …                           ││ Length   3:33            │
╰────────────╯╰─────────────────────────────╯╰──────────────────────────╯
 / Search   Enter Play   o Open   r Refresh   ? Sign in          ^q Quit
```

---

## Table of contents

- [Features](#features)
- [Quick start](#quick-start)
- [Requirements](#requirements)
- [Documentation](#documentation)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Features

- **YouTube-like layout** — a left Library nav (Home, History, Liked, Watch Later,
  Playlists), a results list, and a preview pane.
- **Sign in for your feed** — browse your subscriptions feed, watch history, liked
  videos, watch later, and playlists. Auth is via a browser-exported cookies file
  (no passwords). See the [accounts guide](docs/accounts.md).
- **In-terminal playback** — videos play inside the terminal via mpv, using the
  kitty graphics protocol, sixel, or a truecolor-text fallback depending on your
  terminal.
- **Inline thumbnails** — the highlighted video's thumbnail renders in the
  preview pane, scaling with the window while preserving its 16:9 ratio.
- **Real YouTube data** — powered by `yt-dlp`; no Google API key required.
- **Keyboard-first** — search, browse, switch tabs, and play without the mouse.
- **Modern, refined UI** — a dark theme with a light-red (`#ff6b6b`) accent.
- **Adaptive rendering** — automatically detects the best graphics mode for your
  terminal, with graceful fallbacks everywhere.
- **Self-contained** — ships its own up-to-date `yt-dlp` in a virtualenv, so
  playback doesn't break on a stale system binary.

## Quick start

```bash
# Prerequisites: Python 3.10+ and mpv must be installed.
git clone <your-fork-or-copy> BoxTube   # or use this directory directly
cd BoxTube

python3 -m venv .venv
.venv/bin/pip install -e .                            # installs deps + the CLI
ln -sf "$PWD/.venv/bin/boxtube" ~/.local/bin/boxtube  # put it on your PATH

boxtube   # run from anywhere
```

Then type a query, press **Enter**, browse with **↑/↓**, and press **Enter**
again to watch. See the [usage guide](docs/usage.md) for the full workflow.

## Requirements

| Requirement | Why | Notes |
|-------------|-----|-------|
| Python 3.10+ | Runtime | |
| [mpv](https://mpv.io/) | In-terminal video playback | System package |
| `yt-dlp` | Search + stream resolution + feeds | Installed into the venv via pip |
| A 24-bit color terminal | Rendering | kitty / Ghostty / WezTerm give the sharpest thumbnails & video |
| A YouTube cookies file | Personalized feeds (optional) | Export from your browser; see [accounts](docs/accounts.md). Search works without it |

See the [installation guide](docs/installation.md) for platform-specific notes
(WSL, Ghostty, kitty, sixel terminals).

## Documentation

Full documentation lives in [`docs/`](docs/):

| Guide | Contents |
|-------|----------|
| [Installation](docs/installation.md) | Prerequisites, install, PATH setup, uninstall, platform notes |
| [Accounts / sign-in](docs/accounts.md) | Exporting cookies, the cookies path, what each tab shows |
| [Usage](docs/usage.md) | UI tour, keybindings, search & playback workflows |
| [Configuration](docs/configuration.md) | Environment variables, video-output modes, tunables |
| [Architecture](docs/architecture.md) | Components, data flow, threading model, design decisions |
| [Troubleshooting](docs/troubleshooting.md) | Common problems and fixes |
| [Development](docs/development.md) | Dev setup, project structure, testing, releases |

Project meta: [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)
· [Security policy](SECURITY.md) · [Changelog](CHANGELOG.md)

## Project layout

```
BoxTube/
├── boxtube/                 # application package
│   ├── app.py               # Textual UI + controller (nav, feeds, drill-down)
│   ├── youtube.py           # yt-dlp search/feeds + binary discovery
│   ├── account.py           # sign-in state via a cookies file
│   ├── thumbnails.py        # background thumbnail fetch + cache
│   ├── player.py            # mpv in-terminal playback
│   ├── boxtube.tcss         # theme (light-red accent)
│   └── __main__.py          # `python -m boxtube` entry point
├── docs/                    # documentation
├── tests/                   # test suite
├── boxtube.sh               # local launcher
├── pyproject.toml           # packaging + dependencies + entry point
├── requirements.txt         # pinned runtime deps (mirror of pyproject)
└── Makefile                 # common dev tasks
```

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[development guide](docs/development.md) before opening a pull request, and abide
by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). Please do not file
public issues for security problems.

## License

BoxTube is released under the [MIT License](LICENSE).
