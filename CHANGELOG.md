# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Settings screen + config file**: press **`,`** (or click the **⚙** in the
  header) to open an in-app Settings dialog for video resolution, frame width/rate,
  image backend, capture format, thumbnail cache, grid density, and playback
  cookies. Settings persist to `~/.config/boxtube/config.toml` (override with
  `BOXTUBE_CONFIG`) and apply without a restart — grid density live, player
  settings on the next video. A shell-set `BOXTUBE_*` env var still wins.
- **Channel Videos / Shorts tabs**: drilling into a subscribed channel now shows a
  Videos | Shorts toggle above the grid; switching to Shorts loads that channel's
  Shorts tab and renders them as vertical cards.
- **Vertical Shorts view**: the Shorts feed now renders as tall 9:16 cards using
  YouTube's vertical thumbnail, in a tighter grid of narrower columns, so it reads
  as Shorts rather than wide video cards. Cached thumbnails are bounded to 640px
  on the long edge to keep memory/render cost in check.
- **Loading skeletons**: while a feed loads, the grid now fills with gently
  pulsing placeholder cards instead of going blank under a "Loading…" title —
  clearer feedback and a steadier layout as results arrive.
- **Duration badges on thumbnails**: every video thumbnail (grid cards and the
  preview pane) now carries a YouTube-style duration pill in the bottom-right
  corner, baked into the image so it shows on every terminal backend. The card
  meta line drops to channel · views, and cards gain a hover highlight.
- **Playlist-aware player / autoplay**: the player now carries the whole feed you
  opened from. Press **`n`** / **`b`** to move to the next/previous video in place.
  Opening from the **Shorts** feed enables **autoplay** — when a Short ends it
  rolls straight into the next one (the title shows e.g. `3/40`), stopping at the
  end of the feed. Other feeds enable `n` / `b` without autoplaying.
- **Shorts**: a new **Shorts** filter chip loads a feed of YouTube Shorts
  aggregated from the Shorts tabs of the channels you're subscribed to
  (`youtube.shorts_feed` → `subscription_shorts`, fetched concurrently and
  interleaved round-robin so no single channel dominates). Falls back to the
  public `#shorts` hashtag when signed out. Shorts play through the normal
  player (they appear pillarboxed, being vertical).
- **Thumbnail grid**: videos now render in a responsive grid of focusable cards
  (thumbnail + title + channel · views · duration) instead of a list. Arrow keys
  move through the grid, Enter/double-click plays, and the column count adapts to
  the window width. The preview pane shows a richer view of the highlighted video
  (larger thumbnail, channel, views/length, link, description).
- **YouTube-styled UI**: a header with the ▶ logo, a centered search bar, and a
  sign-in indicator; a row of clickable **filter chips** (All / Music / Gaming /
  …) that run searches; and a sidebar reorganized into a **You** group and a
  **Subscriptions** group that lists your subscribed channels. Clicking a channel
  drills into its videos (`youtube.subscribed_channels` / `channel_videos` via
  `/feed/channels`). Near-black `#0f0f0f` theme.
- **Custom in-terminal video player** with mouse-driven controls. mpv now runs
  headless as an A/V engine controlled over its JSON IPC socket; BoxTube samples
  the current frame into a Textual `Image` widget and draws its own crisp control
  bar — play/pause, skip ±5s, a clickable seek bar, volume bar, and time — all
  mouse-clickable, plus keyboard shortcuts (space, ←/→, ↑/↓, q). New modules
  `boxtube/engine.py` (mpv IPC) and `boxtube/player_screen.py` (the player UI).
  Playback no longer takes over the terminal via suspend.
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
- Hardware video decoding via mpv `--hwdec` (`BOXTUBE_HWDEC`, default `auto-safe`).
- Bounded LRU thumbnail cache (`BOXTUBE_THUMB_CACHE_SIZE`, default 64).
- `docs/accounts.md` sign-in guide; `tests/test_account.py`; expanded tests.
- Comprehensive documentation set under `docs/` (installation, usage,
  configuration, architecture, troubleshooting, development).
- Project meta files: `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, `CHANGELOG.md`.
- `Makefile` with common developer tasks and a `tests/` suite.

### Changed
- **Crisper in-terminal video, with quality now tunable.** Frames are sized to the
  video widget's actual on-screen pixel area and downscaled with a high-quality
  LANCZOS filter; capture JPEG quality rose from 80 to **92**. Defaults stay at
  360p / 480px wide to keep playback smooth (mpv's per-frame screenshots and sixel
  encoding get heavy at higher resolutions, especially on sixel under WSL). The
  active image backend is shown in the player title bar. New knobs let you trade
  smoothness for sharpness on a fast graphics terminal: `BOXTUBE_PLAYER_MAXWIDTH`,
  `BOXTUBE_IMAGE_BACKEND` (force sixel/kitty/halfcell/…), `BOXTUBE_SCREENSHOT_FORMAT`
  (`jpg`/`png`), `BOXTUBE_SCREENSHOT_QUALITY`.
- The main **grid** and **preview** panel borders are now the light-red accent
  (`#ff6b6b`) instead of grey, for a stronger framed look.
- `youtube.search()` and `player.play()` now accept an optional `cookies`
  argument; feed loaders share one internal yt-dlp runner.
- **Player performance**: decoupled frame capture from rendering — a daemon
  thread captures into a "latest frame" slot and a steady UI timer renders it,
  dropping stale frames. This removes the jitter from mpv's variable screenshot
  latency. Capture is skipped while paused, frames are smaller (≤360p, 480px
  wide), and re-renders are suppressed when the frame is unchanged. Tunable via
  `BOXTUBE_PLAYER_FPS` and `BOXTUBE_PLAYER_HEIGHT`.
- **Grid performance**: thumbnails now load lazily and visible-first — only cards
  on screen (plus a small buffer) are fetched/rendered, re-scanning as you scroll,
  so a feed no longer loads every off-screen thumbnail up front. Card thumbnails
  are pre-resized off the UI thread for cheaper re-renders, and the scan trigger
  is debounced so rapid scrolling doesn't restart the loader on every event.

### Fixed
- Playback no longer silently fails when signed in. Sending cookies to mpv broke
  extraction (the JS-free `android_vr`/`tv` clients don't support authenticated
  requests, forcing the JS-dependent `web` client). Cookies are no longer sent to
  playback by default; opt in with `BOXTUBE_PLAYBACK_COOKIES` for private/
  members-only videos. Age-restricted videos still play cookie-free.
- mpv no longer runs with `--really-quiet`, which had suppressed error messages —
  playback failures are now visible.
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
