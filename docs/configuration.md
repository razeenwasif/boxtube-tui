# Configuration

BoxTube favors zero-configuration defaults with sensible auto-detection. The few
knobs that exist are documented here.

## Environment variables

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `BOXTUBE_VO` | `kitty`, `sixel`, `tct`, or any valid mpv `--vo` | auto-detected | Forces the mpv video output used for playback |

### Video output (`BOXTUBE_VO`)

Playback renders video into the terminal using an mpv *video output* (`--vo`).
BoxTube auto-detects the best one; override it when detection guesses wrong or you
want a specific mode:

```bash
BOXTUBE_VO=sixel boxtube
```

| Value | Terminal support | Quality |
|-------|------------------|---------|
| `kitty` | kitty, Ghostty, WezTerm (kitty graphics protocol) | Sharp, photographic |
| `sixel` | foot, mlterm, xterm `-ti vt340` (sixel) | Photographic |
| `tct` | Any 24-bit color terminal (truecolor text blocks) | Blocky, universal |

#### Auto-detection logic

Implemented in `boxtube/player.py::detect_vo()`:

1. If `BOXTUBE_VO` is set, use it verbatim.
2. If `$KITTY_WINDOW_ID` is set, `$TERM` contains `kitty`, or
   `$TERM_PROGRAM == ghostty` → **`kitty`**.
3. If `$WEZTERM_PANE` is set → **`kitty`**.
4. If `$TERM` contains `sixel`, or is `foot` / `mlterm` → **`sixel`**.
5. Otherwise → **`tct`** (the universal fallback).

## Tunable defaults (in code)

These are not environment variables today; they live as small, well-commented
constants in the source. They're documented here because they shape behavior and
are the natural first place to customize.

| Setting | Location | Default | Notes |
|---------|----------|---------|-------|
| Search result limit | `boxtube/app.py` (`search(query, limit=25)`) | 25 | Max results per search |
| Playback resolution cap | `boxtube/player.py` (`--ytdl-format`) | ≤480p | Lower res starts faster; identical once rendered |
| Thumbnail source | `boxtube/youtube.py` (`Video.thumbnail_url`) | `i.ytimg.com/.../mqdefault.jpg` | Clean 320×180 16:9 frame |
| Description truncation | `boxtube/app.py` (`_show_details`) | 1500 chars | Keeps the preview pane tidy |
| Accent color | `boxtube/boxtube.tcss` (`#ff6b6b`) | light red | Theme accent |

## Theming

All colors, borders, spacing, and layout live in
[`boxtube/boxtube.tcss`](../boxtube/boxtube.tcss), a Textual CSS file. Because the
install is editable, edits take effect on the next launch — no rebuild required.
The accent is `#ff6b6b` (with `#ff8a8a` for highlighted text); change those to
re-skin the app.

The thumbnail keeps its aspect ratio via `width: auto` plus a percentage
`height`, so it scales with the window without stretching. See
[architecture → rendering](architecture.md#rendering--graphics) for why.

## yt-dlp resolution

BoxTube deliberately prefers the `yt-dlp` installed **next to the running Python
interpreter** (i.e. the project venv) over any copy on `PATH`. The logic is in
`boxtube/youtube.py::find_ytdlp()`:

1. Look for `yt-dlp` (or `yt-dlp.exe`) beside `sys.executable`.
2. Fall back to `shutil.which("yt-dlp")`.

Both search and mpv's downloader (`--script-opts=ytdl_hook-ytdl_path=…`) use this
resolved path, guaranteeing playback uses the up-to-date, pip-managed `yt-dlp`
even if an older one exists at `/usr/bin/yt-dlp`. Keep it current with:

```bash
.venv/bin/pip install -U yt-dlp     # or: make update-ytdlp
```
