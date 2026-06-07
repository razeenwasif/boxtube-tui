# Configuration

BoxTube favors zero-configuration defaults with sensible auto-detection. The few
knobs that exist are documented here.

## Environment variables

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `BOXTUBE_VO` | `kitty`, `sixel`, `tct`, or any valid mpv `--vo` | auto-detected | Forces the mpv video output used for playback |
| `BOXTUBE_COOKIES` | Path to a cookies.txt | `~/.config/boxtube/cookies.txt` | Where BoxTube reads your YouTube cookies for personalized feeds |
| `BOXTUBE_JS_RUNTIME` | Runtime spec, e.g. `deno`, `node:/opt/node/bin`, or empty | auto-detected | JS runtime passed to yt-dlp; empty disables auto-detection |
| `BOXTUBE_PLAYBACK_COOKIES` | any non-empty value | unset (off) | Send your cookies to mpv during playback (needed for private/members-only videos; breaks normal playback unless a full JS solver is set up) |
| `BOXTUBE_HWDEC` | mpv `--hwdec` mode, or empty | `auto-safe` | Hardware video decoding mode passed to mpv; empty omits the option |
| `BOXTUBE_THUMB_CACHE_SIZE` | integer | `64` | Max thumbnails kept in the in-memory LRU cache (`0` disables caching) |
| `BOXTUBE_PLAYER_FPS` | integer (1–60) | `15` | Player render/capture frame rate |
| `BOXTUBE_PLAYER_HEIGHT` | integer (144–1080) | `360` | Max video height the player streams/decodes |
| `XDG_CONFIG_HOME` | Path | `~/.config` | Base dir for the default cookies path |

### Sign-in / cookies (`BOXTUBE_COOKIES`)

Personalized tabs (Home, History, Liked, Watch Later, Playlists) read a
browser-exported cookies file. By default that's
`~/.config/boxtube/cookies.txt`; point `BOXTUBE_COOKIES` elsewhere to use a
different file:

```bash
BOXTUBE_COOKIES=/secure/yt-cookies.txt boxtube
```

See the [accounts guide](accounts.md) for how to export the file. Search works
without it.

### JavaScript runtime (`BOXTUBE_JS_RUNTIME`)

Recent yt-dlp uses a JavaScript runtime to solve YouTube's challenges and expose
the full set of formats. During playback BoxTube **auto-detects** a locally
installed, Linux-native runtime — it looks for `deno`, `bun`, `node`, then `qjs`
(skipping Windows `.exe`s under `/mnt` on WSL) — and passes it to yt-dlp as
`--js-runtimes`. This complements the JS-free `android_vr`/`tv` client fallback,
so playback works with or without a runtime.

Override or disable detection:

```bash
BOXTUBE_JS_RUNTIME=deno boxtube          # force a specific runtime
BOXTUBE_JS_RUNTIME=node:/opt/node/bin    # ... with an explicit location
BOXTUBE_JS_RUNTIME= boxtube              # disable (empty value)
```

> To let the runtime fully solve challenges, yt-dlp may also need its EJS solver
> script. That involves a remote download and is left opt-in — see
> [troubleshooting](troubleshooting.md#playback-fails-requested-format-is-not-available).

### Playback cookies (`BOXTUBE_PLAYBACK_COOKIES`)

By default BoxTube does **not** send your cookies to mpv during playback, even
when signed in. The JS-free `android_vr`/`tv` clients used for reliable playback
don't support authenticated requests, so passing cookies forces the JS-dependent
`web` client and breaks extraction ("Requested format is not available").
Age-restricted videos already play **without** cookies via those clients.

Set `BOXTUBE_PLAYBACK_COOKIES=1` only if you need to play **private** or
**members-only** videos *and* have a working JS solver configured — otherwise it
will break normal playback.

### Player performance (`BOXTUBE_PLAYER_FPS`, `BOXTUBE_PLAYER_HEIGHT`)

The player captures frames from mpv and renders them on a steady timer,
independent of mpv's (variable) screenshot latency, dropping stale frames. Two
knobs trade smoothness for CPU:

```bash
BOXTUBE_PLAYER_FPS=20 boxtube       # smoother, more CPU
BOXTUBE_PLAYER_FPS=10 boxtube       # lighter, less smooth
BOXTUBE_PLAYER_HEIGHT=240 boxtube   # smaller frames = cheaper capture/transmit
```

If playback feels choppy on a slower machine or terminal, **lower** the fps (and
optionally the height). On a fast graphics terminal you can **raise** the fps.
While paused, the player stops capturing entirely (a paused frame never changes),
so it idles cheaply. The per-frame render cost is dominated by your terminal's
image backend (kitty graphics is cheapest; sixel/half-block cost more).

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
| Playback resolution cap | `BOXTUBE_PLAYER_HEIGHT` (engine `--ytdl-format`) | ≤360p | Lower res starts faster; tune for your terminal |
| Player display width | `boxtube/player_screen.py` (`DISPLAY_WIDTH`) | 480px | Frames resized before render to bound work |
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
