# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **YouTube-like layout**: a three-pane UI with a left Library nav (Home,
  History, Liked, Watch Later, Playlists), results list, and preview pane.
- **Sign-in via a cookies file** (`boxtube/account.py`): browse your
  subscriptions feed, watch history, liked videos, watch later, and playlists.
  Cookies are read from `~/.config/boxtube/cookies.txt` (override with
  `BOXTUBE_COOKIES`). In-app sign-in instructions (`?`) and a status indicator.
- **Playlists drill-down**: open a playlist to view its videos; `Backspace` to go
  back.
- New keybindings: `1`–`5` (jump to tab), `r` (refresh), `?` (sign-in help),
  `Backspace` (back).
- Cookies are passed to mpv during playback so age-restricted/private videos play.
- Auto-detects a local JavaScript runtime (`deno`/`bun`/`node`/`qjs`, Linux-native)
  and passes it to yt-dlp as `--js-runtimes` during playback. Override or disable
  with `BOXTUBE_JS_RUNTIME`.
- `docs/accounts.md` sign-in guide; `tests/test_account.py`; expanded tests.
- Comprehensive documentation set under `docs/` (installation, usage,
  configuration, architecture, troubleshooting, development).
- Project meta files: `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, `CHANGELOG.md`.
- `Makefile` with common developer tasks and a `tests/` suite.

### Changed
- `youtube.search()` and `player.play()` now accept an optional `cookies`
  argument; feed loaders share one internal yt-dlp runner.

### Fixed
- Personalized feeds that fail because of expired/incomplete cookies now show a
  clear in-app "Your sign-in isn't working" panel with re-export steps (private
  window), instead of a vague "No results". Detected from empty feeds while
  signed in and from auth-style yt-dlp errors (e.g. "playlist does not exist").
- Playback no longer fails with "Requested format is not available" on videos
  where YouTube's `web` client returns a degraded format set without a JS
  runtime: BoxTube now forces the JS-free `android_vr`/`tv` clients and ends the
  format chain with an uncapped fallback.
- "Open in browser" (`o`) now works on WSL, routing to the Windows browser via
  `wslview` or `cmd.exe start` instead of failing through `xdg-open`
  (new `boxtube/opener.py`).

## [0.1.0] - 2026-06-06

### Added
- TUI YouTube client built with [Textual](https://textual.textualize.io/).
- YouTube search via `yt-dlp` (flat playlist dump), no API key required.
- In-terminal video playback via `mpv`, with automatic video-output detection
  (kitty graphics protocol / sixel / truecolor text) and a `BOXTUBE_VO`
  override.
- Inline thumbnail previews via `textual-image`, fetched in the background,
  cached, and aspect-ratio preserving across window sizes.
- Modern dark theme with a light-red (`#ff6b6b`) accent.
- `boxtube` console entry point, installable on `PATH`.
- Bundled, up-to-date `yt-dlp` (resolved from the venv) so playback does not
  depend on a stale system binary.

[Unreleased]: https://github.com/razeenwasif/boxtube-tui/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/razeenwasif/boxtube-tui/releases/tag/v0.1.0
