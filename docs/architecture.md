# Architecture

This document describes how BoxTube is structured, how data flows through it, and
the key design decisions behind it.

## Overview

BoxTube is a single-process [Textual](https://textual.textualize.io/) application.
It orchestrates three external concerns — **search**, **thumbnails**, and
**playback** — around a keyboard-driven UI. It has no server, no database, and no
persistent state beyond an in-memory thumbnail cache for the session.

```
            ┌───────────────────────────────────────────────┐
            │                  boxtube.app                   │
            │      (Textual App: UI + event controller)      │
            └───────────────────────────────────────────────┘
                 │              │                  │
        search   │     thumbnail│ fetch    playback│
                 ▼              ▼                  ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ boxtube.     │ │ boxtube.     │ │ boxtube.     │
        │   youtube    │ │  thumbnails  │ │   player     │
        └──────────────┘ └──────────────┘ └──────────────┘
                 │              │                  │
                 ▼              ▼                  ▼
            yt-dlp (CLI)   i.ytimg.com         mpv (CLI)
          ytsearch dump    HTTPS + Pillow    in-terminal video
```

## Modules

| Module | Responsibility | Key surface |
|--------|----------------|-------------|
| `boxtube/app.py` | Textual UI, layout, nav, events, orchestration | `BoxTube(App)`, `NavItem`/`VideoItem`/`PlaylistItem`, `main()` |
| `boxtube/youtube.py` | Search & personalized feeds via `yt-dlp`; binary discovery; models & formatting | `search()`, `videos_for_feed()`, `user_playlists()`, `Video`, `Playlist`, `find_ytdlp()` |
| `boxtube/account.py` | Sign-in state from a cookies file | `is_signed_in()`, `cookies_arg()`, `cookies_path()` |
| `boxtube/thumbnails.py` | Download + cache thumbnails as PIL images | `fetch()`, `placeholder()` |
| `boxtube/engine.py` | Headless mpv A/V engine controlled over the JSON IPC socket | `MpvEngine` (`start`, `get`/`set`, `seek`, `screenshot`, `quit`) |
| `boxtube/player_screen.py` | Custom player UI: frame pump + mouse-driven control bar | `PlayerScreen`, `ClickBar` |
| `boxtube/player.py` | mpv video-output / hwdec detection (used by the engine) | `detect_vo()`, `detect_hwdec()`, `mpv_path()` |
| `boxtube/opener.py` | Open links in a browser (WSL-aware) | `open_url()`, `is_wsl()` |
| `boxtube/boxtube.tcss` | Theme: colors, borders, layout | (Textual CSS) |
| `boxtube/__main__.py` | `python -m boxtube` entry | delegates to `app.main` |

The dependency direction is acyclic: `app` → {`youtube`, `account`, `thumbnails`,
`player`}, and `player` → `youtube` (for `find_ytdlp`). Nothing imports `app`.

## Navigation & data sources

The left nav (`NAV_ITEMS` in `app.py`) maps each tab to a yt-dlp target:

| Tab | Loader | yt-dlp target | Auth |
|-----|--------|---------------|------|
| Home | `youtube.subscriptions_feed` | `/feed/subscriptions` | cookies |
| History | `youtube.watch_history` | `/feed/history` | cookies |
| Liked | `youtube.liked_videos` | `playlist?list=LL` | cookies |
| Watch Later | `youtube.watch_later` | `playlist?list=WL` | cookies |
| Playlists | `youtube.user_playlists` → `playlist_videos` | `/feed/playlists` → `playlist?list=<id>` | cookies |
| Search (top bar) | `youtube.search` | `ytsearchN:<query>` | none |

All feed loaders funnel through one internal runner, `youtube._entries(target,
limit, cookies)`, which runs `yt-dlp --flat-playlist --dump-json` (adding
`--cookies` and `--playlist-end` as needed) and parses the JSON lines. Helpers
split the results into `Video`s and `Playlist`s (`_is_video_entry` /
`_is_playlist_entry`), so a feed that mixes both is handled correctly.

**Sign-in** is just the presence of a non-empty cookies file (`account`). Opening
an auth tab while signed out renders in-app sign-in steps instead of calling
yt-dlp. **Playlists** is a two-level view: the list of playlists, then a selected
playlist's videos (`Backspace` returns), tracked by `self._drill_playlist`.

## UI composition

`BoxTube.compose()` builds the widget tree:

```
Screen
├── #appbar (Horizontal)        app bar: brand + hint
├── #search (Input)             query box
├── #body (Horizontal)
│   ├── #results (ListView)     VideoItem rows (title + meta)
│   └── #detail-pane (VerticalScroll)
│       ├── #thumb (Image)      textual-image widget
│       ├── #meta (Static)      title / channel / length / views / link
│       └── #desc (Static)      description
└── Footer                      keybindings
```

Selection state is tracked by `self._current_video_id`, used to discard
out-of-order thumbnail loads (see below).

## Data flow

### Search

```
User types query, presses Enter
        │  Input.Submitted
        ▼
BoxTube.run_search()           @work(thread=True, exclusive, group="search")
        │  (worker thread)
        ▼
youtube.search(query, 25)      subprocess: yt-dlp "ytsearch25:query"
        │                                  --flat-playlist --dump-json
        │  list[Video]
        ▼
call_from_thread(_populate)    (UI thread) clear + append VideoItem rows,
                                            highlight first, show details
```

`youtube.search()` runs `yt-dlp` with `--flat-playlist --dump-json`, which emits
one JSON object per result without resolving stream URLs — fast and cheap. Each
line is parsed into a `Video` dataclass; malformed lines and playlist entries are
skipped.

### Thumbnail preview

```
Row highlighted → _show_details(video)
        │  set #meta, #desc, reset #thumb to placeholder, record id
        ▼
BoxTube.load_thumbnail(video)  @work(thread=True, exclusive, group="thumb")
        │  (worker thread) thumbnails.fetch(id, url)  → HTTPS + Pillow (cached)
        ▼
call_from_thread(_apply_thumbnail, id, image)
        │  (UI thread) if id == self._current_video_id: set #thumb.image
        ▼
   else: drop (selection already moved on)
```

The `exclusive=True, group="thumb"` worker config cancels an in-flight load when
you navigate again, and the `_current_video_id` guard ensures a slow download for
a previous row can never overwrite the current preview — eliminating flicker and
races during fast scrolling.

### Playback — custom player (engine + screen)

`Enter`/`p` on a row → `_watch(video)` (guards that mpv is installed) →
`push_screen(PlayerScreen(video))`. Playback is a dedicated `PlayerScreen` rather
than suspending the TUI and handing the terminal to mpv:

```
PlayerScreen.on_mount
   └─ daemon thread: MpvEngine.start()        mpv --vo=null --ao=null
                                              --input-ipc-server=<sock>  (headless)
   └─ daemon thread: capture loop (BOXTUBE_PLAYER_FPS)
        if not paused: engine.screenshot() → read JPEG → resize → self._latest
        always:        engine.get(time-pos/pause/volume) → self._props
   └─ UI timer: render tick (BOXTUBE_PLAYER_FPS)
        latest frame (if changed) → Image widget;  props → control bar
   user input (mouse/keys) → engine.seek / cycle pause / set volume  (over IPC)
```

- **mpv is the single A/V engine and master clock.** It decodes audio + video
  headless; BoxTube samples the *current* frame with `screenshot-to-file … video`,
  so frames are inherently in sync with the audio (no second decoder).
- **Decoupled capture and render.** A daemon thread captures into a shared
  "latest frame" slot; a Textual interval timer renders the latest frame on the UI
  thread at a steady rate, **dropping stale frames**. This smooths the jitter from
  mpv's variable screenshot latency, and renders only when the frame changed
  (so a paused video — which also stops capture — costs nothing).
- **Threads, not workers.** The engine start and capture loop run on plain *daemon*
  threads. Textual's shutdown awaits `@work` workers, which would deadlock against
  an infinite loop; daemon threads are not awaited and poll a `_stop` flag. They
  marshal UI updates with `call_from_thread`.
- **Closing** awaits `pop_screen()` (an un-awaited pop stalls app shutdown) after
  the pump has wound down and mpv has quit. Avoid shadowing Textual
  `MessagePump` internals (e.g. `_closing`, `_running`) on the screen.

mpv resolves the YouTube stream through its bundled *ytdl hook*, pointed at the
venv `yt-dlp` (`--script-opts=ytdl_hook-ytdl_path=…`) so playback never uses a
stale system binary.

## Threading model

Textual runs an async event loop on the **UI thread**. All widget mutation must
happen there. BoxTube pushes blocking work off that thread:

- **Workers** — `@work(thread=True)` runs `run_search` and `load_thumbnail` on
  background threads, keeping the UI responsive during network/subprocess waits.
- **Marshalling** — workers never touch widgets directly; they call
  `self.call_from_thread(...)` to run UI updates back on the event loop.
- **Exclusivity** — `exclusive=True` with a `group` name means a newer task in the
  same group cancels the older one (latest search/thumbnail wins).
- **Playback** runs on dedicated *daemon* threads (the engine start and frame
  pump), marshalling UI updates with `call_from_thread` — see the custom-player
  notes above.

## Rendering & graphics

- **Thumbnails** are rendered by `textual-image`, which picks the terminal's best
  image backend (kitty graphics protocol → sixel → halfcell → unicode). The
  `#thumb` widget uses `width: auto` + a percentage `height` so the library
  derives width from height at the image's true aspect ratio — the preview scales
  with the window and never stretches. See
  [configuration → theming](configuration.md#theming).
- **Video** is rendered by mpv's terminal video outputs, selected by
  `detect_vo()`; see
  [configuration → video output](configuration.md#video-output-boxtube_vo).

## Design decisions & trade-offs

- **`yt-dlp` over the YouTube Data API** — no API key, no quotas, no account; at
  the cost of depending on an actively-maintained scraper that needs updating.
- **Bundled `yt-dlp` in the venv** — playback reliability is gated on `yt-dlp`
  currency; bundling and explicitly resolving it avoids "works on search, fails on
  play" caused by a stale `/usr/bin/yt-dlp`.
- **mpv for playback** — reuses a mature player with built-in YouTube support and
  multiple terminal video backends, instead of reimplementing decoding/rendering.
- **Flat-playlist search** — trades richer per-result metadata for speed; full
  details (and the stream) are resolved lazily only when needed.
- **Headless mpv + frame sampling** — keeping mpv as the single A/V engine (and
  sampling its current frame) gives free audio sync and lets BoxTube draw its own
  crisp, mouse-driven controls, at the cost of a modest sampled framerate.
- **In-memory thumbnail cache** — session-scoped LRU (`BOXTUBE_THUMB_CACHE_SIZE`),
  bounded by what you browse; no disk cache to manage or invalidate.
