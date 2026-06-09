# BoxTube — working context / session handoff

> Pick-up notes for continuing development. For user-facing docs see
> [`README.md`](README.md) and [`docs/`](docs/). This file captures **how the
> code got here and why** — decisions, gotchas, and what's next.

_Last updated: 2026-06-07._

## What BoxTube is

A terminal (TUI) YouTube client built with **Python + [Textual](https://textual.textualize.io/)**.
Search YouTube, sign in to browse your feeds, watch videos **inside the terminal**
via a custom player. Data comes from **`yt-dlp`** (no Google API key). Playback is
**`mpv`** running headless, controlled over its IPC socket. YouTube-styled UI:
header + search, filter chips, sidebar (You + Subscriptions), a thumbnail grid,
and a preview pane.

## Repo & environment

- **GitHub:** `git@github.com:razeenwasif/boxtube-tui.git` (public), branch `main`.
  > The name `boxtube` was already taken by the user's separate React web app
  > (`razeenwasif/boxtube`) — do **not** touch that repo. This is `boxtube-tui`.
- **Latest commit:** `b34840c` · **tag:** `v0.1.0`.
- **Local dir:** `/home/amaterasu/BoxTube` (this is the user's WSL machine).
- **venv:** `.venv/` — Python 3.12, Textual 8.2.7, textual-image, Pillow,
  **yt-dlp 2026.03.17** (bundled in venv; do not rely on the stale system
  `/usr/bin/yt-dlp` 2024.04). mpv 0.37 (system). `bun` is the detected JS runtime.
- **CLI:** `boxtube` is on PATH via `~/.local/bin/boxtube` → `.venv/bin/boxtube`
  (console entry `boxtube.app:main`, editable install).
- **Signed in:** yes — valid cookies at `~/.config/boxtube/cookies.txt` exist on
  this machine, so feeds/subscriptions work live here.
- **Run:** `boxtube` (or `./boxtube.sh`, `.venv/bin/python -m boxtube`).
- **Tests:** `make test` or `.venv/bin/python -m pytest -m "not network" -q`
  → **88 passing** (1 network test deselected by default). Use
  `-p no:cacheprovider` to avoid the cache dir.

## Architecture (modules in `boxtube/`)

| Module | Responsibility |
|--------|----------------|
| `app.py` | Textual UI + controller. Header/chips/sidebar/grid/preview. `BoxTube(App)`, card widgets (`VideoCard`/`PlaylistCard`/`SkeletonCard`/`Card`), `NavItem`/`ChannelItem`/`Chip`, `CardSelected`/`CardActivated` messages. Loads go through `_begin_load` (title + `_show_skeletons` + pulse timer); `_show_grid`/`_on_load_error` stop the pulse. |
| `youtube.py` | yt-dlp search + feeds. `Video`/`Playlist`/`Channel`, `search`, `videos_for_feed`, `shorts_feed` (#shorts hashtag), `user_playlists`/`playlist_videos`, `subscribed_channels`/`channel_videos`, `find_ytdlp`/`find_js_runtime`. One internal runner `_entries`. |
| `account.py` | Sign-in state from a cookies file. `is_signed_in`, `cookies_arg`, `cookies_path`. |
| `config.py` | Persisted user settings (TOML at `~/.config/boxtube/config.toml`, `BOXTUBE_CONFIG` override). `SCHEMA`, `load`/`save`, `apply_to_env` (setdefault at startup, overwrite on save). Most settings map to a `BOXTUBE_*` env var so existing reads pick them up. |
| `settings_screen.py` | `SettingsScreen(ModalScreen)` — in-app editor for the config (`,` / ⚙). Save writes TOML + `apply_to_env(overwrite=True)` + dismisses with values. |
| `thumbnails.py` | Thumbnail download + **LRU cache**; `placeholder`, `for_card` (downscale for grid cells), `with_duration_badge` (bakes a YouTube-style duration pill into the image, all backends). |
| `engine.py` | **Headless mpv** A/V engine over JSON IPC. `MpvEngine` (`start`, `get`/`set`, `seek`, `screenshot`, `quit`). |
| `player_screen.py` | Custom player UI (`PlayerScreen`, `ClickBar`). Frame pump + mouse control bar. Carries a `playlist`/`index`; `_switch_to` plays the next clip in place; `autoplay` (Shorts) advances on EOF; `n`/`b` = next/prev. Frames sized to the widget's pixel area (`_recompute_target`, LANCZOS); image backend via `PlayerImage`/`BOXTUBE_IMAGE_BACKEND`, shown in the title. |
| `player.py` | mpv `--vo`/`--hwdec` detection (`detect_vo`, `detect_hwdec`, `mpv_path`). `build_command`/`play` are legacy (unused by the app now; still tested). |
| `opener.py` | WSL-aware browser open (`open_url`, `is_wsl`). |
| `boxtube.tcss` | Theme — near-black `#0f0f0f`, light-red `#ff6b6b` accent. |

## What was built today (chronological)

1. Initial TUI: search (yt-dlp) → list, in-terminal mpv playback (suspend+handover), red accent.
2. Lighter red, modern theme, **thumbnails** via `textual-image`; preview thumbnail made aspect-correct (no stretch).
3. `boxtube` put on PATH (pyproject entry point + `~/.local/bin` symlink).
4. **Enterprise docs**: README, LICENSE, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, `docs/` guides, Makefile, `tests/`.
5. `git init` + pushed to GitHub as **boxtube-tui**; tagged `v0.1.0`.
6. **Playback fix:** stale system yt-dlp → bundled current yt-dlp in venv; `find_ytdlp` prefers the venv copy. **WSL browser-open** fix (`opener.py`). Auto-pass **`--js-runtimes`** when a runtime is detected.
7. **Sign-in / feeds:** cookies-based auth; surfaced cookie/auth failures with an in-app "your sign-in isn't working" panel (the user's first cookie export was incomplete; re-exporting via a private window fixed it).
8. **Silent-playback-when-signed-in fix:** cookies break extraction (see gotchas). Stopped sending cookies to playback by default; dropped `--really-quiet` so errors show.
9. **Custom player:** `engine.py` (headless mpv IPC) + `player_screen.py` (mouse-driven control bar). Replaced suspend+handover.
10. **Player perf:** decoupled capture/render (steady timer, drop stale frames), skip capture while paused, smaller frames; `BOXTUBE_PLAYER_FPS`/`HEIGHT`.
11. **YouTube-styled UI redesign:** header (logo + centered search + auth), filter **chips**, sidebar grouped into **You** + **Subscriptions** (live subscribed channels via `feed/channels` + cookies), channel drill-down.
12. **Thumbnail grid:** videos render as a responsive grid of focusable cards; richer preview pane.
13. **Grid perf:** lazy **visible-first** thumbnail loading; then **pre-resize** card thumbnails + **debounced** scroll/scan.
17. **UI polish batch:** duration badges baked into thumbnails (`thumbnails.with_duration_badge`); loading **skeletons** (`SkeletonCard` + `_begin_load`/pulse); **vertical Shorts view** (`Video.is_short` → oardefault thumbnail, `SHORTS_CARD_WIDTH` narrower grid, thumbnails capped to 640px); **channel Videos/Shorts tabs** (`#channel-tabs`/`ChannelTab`, `_channel_tab`, `load_channel` branches on tab → `channel_shorts`). Avatar in the channel header was intentionally skipped (needs an extra per-channel fetch, low value in a coarse TUI).
19. **Audio crackle/dropouts fix:** the audio stutter the user heard is mpv's audio thread getting starved when sixel encoding (UI thread) + per-frame `screenshot-to-file` (mpv thread) spike CPU on WSL — *not* bitrate (`bestaudio` ≈130k opus is already max). Engine now adds `--audio-buffer` (`_audio_buffer()`, `BOXTUBE_AUDIO_BUFFER` default 0.6s, also a Settings choice), `--screenshot-high-bit-depth=no`, `--cache=yes`, `--demuxer-readahead-secs=20`; the capture loop polls volume every 12th tick instead of every frame to cut IPC contention. Raise the buffer / lower FPS if it persists.
18. **Settings screen + config file:** `config.py` (TOML, `SCHEMA`, `load`/`save`/`apply_to_env`) + `settings_screen.py` (`SettingsScreen`, `,`/⚙ gear). Player reads settings **per-playback** now (`PlayerScreen.__init__` reads env into `self._fps/_height/_maxw/_image_cls`) so saves apply to the next video without restart; grid density (`self._card_width`) applies live; thumb cache is live. `main()` calls `config.apply_to_env(config.load())` (setdefault → shell env still wins). Accent-color editing was deferred (needs a TCSS `$variable` refactor; risky to do blind).

14. **Shorts:** light-red panel borders (`#grid`/`#detail-pane`); a **Shorts** chip (`run_shorts` → `youtube.shorts_feed`). The `#shorts` hashtag page only yields **one** entry under `--flat-playlist`, so Shorts are instead aggregated from subscribed channels' Shorts tabs (`subscription_shorts`: up to `SHORTS_MAX_CHANNELS=30` channels × `SHORTS_PER_CHANNEL=5`, fetched via a `ThreadPoolExecutor`, interleaved round-robin; channel name stamped from the sub since the Shorts tab omits the uploader). Hashtag is a signed-out fallback. Shorts play in the normal player (pillarboxed, being vertical).
15. **Playlist-aware player / autoplay:** `PlayerScreen` now takes `playlist`/`index`/`autoplay`. `app._watch` passes the current feed (VideoCards) + the clicked index, with `autoplay=self._shorts_active`. EOF routes through `_on_playback_ended` → auto-advance (Shorts) or close; `_switch_to(video)` tears down and restarts the engine in place (guarded by `_switching`); `n`/`b` step the playlist; title shows `i/N`. mpv `--idle=no` means it exits at EOF, which the capture loop already detects.
16. **Video quality (tunable; defaults favour smoothness):** frames sized to the `#pl-video` widget's on-screen pixel area (`_recompute_target` = cells × cell-px from `get_cell_size`, cap `BOXTUBE_PLAYER_MAXWIDTH`); LANCZOS downscale (never upscale); capture JPEG q80→**92** (engine `_screenshot_quality`, optional PNG via `BOXTUBE_SCREENSHOT_FORMAT`). **Gotcha — don't raise the defaults:** mpv takes an on-demand `screenshot-to-file` inside its playback loop every frame, so higher `PLAYER_HEIGHT` stutters **audio**; sixel encodes on the UI thread per tick, so larger `MAX_DISPLAY_WIDTH` lags **video**. Both worst on sixel-under-WSL. So defaults reverted to the known-smooth **360p / 480px** (an earlier 480p/960px attempt regressed audio+lag); raise only on a cheap-transmit kitty terminal. Backend selectable via `BOXTUBE_IMAGE_BACKEND` (else textual-image auto-detect; **must use the resolved `widget.Image` = `SixelImage` on sixel — `AutoImage` renders black on sixel**), shown in the title (`_active_backend`). **Audio already maxed** (`bestaudio` ≈130k opus; no higher tier without Premium auth, which breaks extraction) — no audio knob.

## Key decisions & gotchas (read before changing related code)

- **Never send cookies to mpv playback by default.** The JS-free
  `android_vr`/`tv` clients (needed for reliable extraction without a JS solver)
  don't support authenticated requests, so cookies force the `web` client →
  "Requested format is not available". Search/feeds DO use cookies. Playback
  cookies are opt-in via `BOXTUBE_PLAYBACK_COOKIES` (and only work with a full JS
  solver). Age-restricted videos already play cookie-free via android_vr/tv.
- **Don't shadow Textual `MessagePump` internals on widgets/screens.** `_closing`,
  `_closed`, `_running` are live framework attributes — a screen attribute named
  `_closing` broke `pop_screen` and hung shutdown. (Player uses `_close_started`.)
- **Player threading:** the engine start + frame pump run on plain **daemon
  threads**, not `@work` workers — Textual's shutdown awaits workers and would
  deadlock an infinite pump. Closing the screen must **await `pop_screen()`** (an
  un-awaited pop stalls shutdown).
- **yt-dlp currency matters.** Bundled in venv; `find_ytdlp()` prefers the copy
  next to `sys.executable`. If playback/feeds break later: `make update-ytdlp`.
- **Cookies must be a complete export** (first-party login cookies: `SID`,
  `SAPISID`, `__Secure-1PSID`, `LOGIN_INFO`). Use a **private window, export, then
  close it** (browsers rotate/invalidate cookies). The app detects bad cookies and
  shows re-export steps.
- **Dead yt-dlp endpoints:** `feed/trending` and `feed/channels` *without* cookies.
  `feed/channels` *with* cookies works (subscribed channels).
- **Grid lazy-load timing:** thumbnails only load once card regions are laid out;
  the worker waits for `_grid_layout_ready()` before scanning. Visibility is
  region-based (`_visible_unloaded_cards`).
- **Tests must stay offline/fast:** `tests/test_app.py`'s `_offline` autouse
  fixture stubs `account` + the `youtube` loaders so signed-in code paths in
  `on_mount` don't hit the network. The screenshot `Screenshot*.png` in root is
  gitignored.

## Environment variables

`BOXTUBE_VO` (kitty/sixel/tct), `BOXTUBE_COOKIES`, `BOXTUBE_JS_RUNTIME`,
`BOXTUBE_PLAYBACK_COOKIES`, `BOXTUBE_HWDEC`, `BOXTUBE_THUMB_CACHE_SIZE`,
`BOXTUBE_PLAYER_FPS` (default 15), `BOXTUBE_PLAYER_HEIGHT` (default 360).
See [`docs/configuration.md`](docs/configuration.md).

## Workflow conventions

- **Update ALL affected docs + `CHANGELOG.md` before every commit** (there's a
  saved memory enforcing this). Stage docs with code.
- Run `pytest -m "not network"` before pushing.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Verify UI changes by exporting an SVG screenshot (`app.save_screenshot`) and
  converting with `cairosvg` to PNG to view. Note: `textual-image` thumbnails and
  rounded borders/emoji show as `□`/blank in the PNG export (export-font artifact)
  but render fine in a real terminal.

## Known limitations & next steps

- **Perf, terminal-bound:** the remaining cost is the terminal's image backend
  painting visible thumbnails (kitty-graphics cheap; half-block ~6µs/cell). Next:
  **profile on the user's real terminal** (Ghostty / Windows Terminal under WSL —
  check `$TERM`). Options if janky: force kitty-graphics where supported, cap
  visible thumbnail size/count, or a density toggle.
- **Player:** ~15 fps sampled frames; quality depends on terminal (sharp on
  kitty/Ghostty, blocky on half-block/tct). The dev env here is `xterm-256color`
  so it falls back to `tct`.
- **Chips** are static categories that just run searches (not dynamic/contextual).
- **CHANGELOG** `[0.1.0]` release link 404s until a GitHub Release is created
  (only the tag exists).
- Possible future: per-row/grid thumbnails for playlists, channels list richness,
  watch history write-back, config file instead of env vars.
