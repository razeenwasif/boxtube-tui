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
| `boxtube/player.py` | Build & run the mpv command; choose a video output | `play()`, `build_command()`, `detect_vo()`, `mpv_path()` |
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

### Playback

```
Enter / p on a row → _watch(video)
        │  guard: mpv installed?
        │  pick vo = detect_vo()
        ▼
with app.suspend():            Textual releases the terminal
        player.play(url, vo)   subprocess.run(mpv … url), blocks until exit
        ▼
(resume) refocus results
```

mpv resolves the YouTube stream itself through its bundled *ytdl hook*, which
shells out to `yt-dlp`. BoxTube points the hook at the venv `yt-dlp`
(`--script-opts=ytdl_hook-ytdl_path=…`) so playback never uses a stale system
binary. The TUI is suspended for the duration so mpv owns the terminal.

## Threading model

Textual runs an async event loop on the **UI thread**. All widget mutation must
happen there. BoxTube pushes blocking work off that thread:

- **Workers** — `@work(thread=True)` runs `run_search` and `load_thumbnail` on
  background threads, keeping the UI responsive during network/subprocess waits.
- **Marshalling** — workers never touch widgets directly; they call
  `self.call_from_thread(...)` to run UI updates back on the event loop.
- **Exclusivity** — `exclusive=True` with a `group` name means a newer task in the
  same group cancels the older one (latest search/thumbnail wins).
- **Playback** is intentionally *synchronous and blocking* inside
  `app.suspend()`: while a video plays, the TUI should be paused anyway.

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
- **Suspend-and-run playback** — simpler and more robust than embedding video in a
  widget, and gives the sharpest output since mpv drives the terminal directly.
- **In-memory thumbnail cache** — session-scoped, bounded by what you browse; no
  disk cache to manage or invalidate.
