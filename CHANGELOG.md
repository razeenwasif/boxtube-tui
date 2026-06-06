# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation set under `docs/` (installation, usage,
  configuration, architecture, troubleshooting, development).
- Project meta files: `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, `CHANGELOG.md`.
- `Makefile` with common developer tasks and a `tests/` suite.

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
