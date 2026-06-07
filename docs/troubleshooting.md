# Troubleshooting

Common problems and how to fix them. If your issue isn't here, see
[architecture](architecture.md) to understand the moving parts, or open an issue
(include your OS, terminal, and `mpv --version` / `.venv/bin/yt-dlp --version`).

## Playback fails: "Failed to open https://…googlevideo.com/…"

**Symptom**

```
Failed to open https://rrN---…googlevideo.com/videoplayback?…
EDL: Could not open source file '…'
No video or audio streams selected.
```

**Cause** — almost always an **outdated `yt-dlp`**. YouTube changes its stream
cipher frequently; an old `yt-dlp` produces URLs that come back HTTP 403. Search
and thumbnails keep working because they don't need stream deciphering.

**Fix**

```bash
.venv/bin/pip install -U yt-dlp     # or: make update-ytdlp
```

Confirm BoxTube is using the fresh copy (it prefers the venv one):

```bash
.venv/bin/python -c "from boxtube.youtube import find_ytdlp; print(find_ytdlp())"
.venv/bin/yt-dlp --version
```

See [configuration → yt-dlp resolution](configuration.md#yt-dlp-resolution).

## Playback fails: "Requested format is not available"

**Cause** — recent yt-dlp needs a JavaScript runtime for YouTube's default `web`
client; without one it returns a degraded format set, and mpv's hook can't find a
stream matching the resolution cap. BoxTube works around this by forcing the
JS-free `android_vr`/`tv` clients (`--ytdl-raw-options-append=extractor-args=...`
in `player.py`) and by ending the format chain with an uncapped fallback, so this
should not happen.

BoxTube also auto-detects a local JS runtime (`deno`/`bun`/`node`/`qjs`) and
passes it to yt-dlp as `--js-runtimes` during playback — see
[configuration](configuration.md#javascript-runtime-boxtube_js_runtime).

If you still hit it:

- Update yt-dlp: `.venv/bin/pip install -U yt-dlp` (or `make update-ytdlp`).
- Install a JS runtime if you don't have one — yt-dlp recommends
  [deno](https://deno.com/). BoxTube will pick it up automatically (or set
  `BOXTUBE_JS_RUNTIME`).
- For yt-dlp to *fully* solve JS challenges, the runtime needs its EJS solver
  script, which yt-dlp downloads on demand. That's a remote fetch BoxTube does
  **not** enable for you; to opt in, run a one-off yt-dlp command with
  `--remote-components ejs:github` (see the
  [yt-dlp EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS)).

## "open in browser" does nothing / xdg-open errors (WSL)

On WSL there's often no Linux browser, so `xdg-open` fails with a list of
"not found" lines. BoxTube detects WSL and opens links via `wslview` (from the
`wslu` package) or `cmd.exe start` instead. For the nicest experience install
`wslu`:

```bash
sudo apt install wslu
```

## "mpv is not installed"

BoxTube can't find mpv on your `PATH`.

```bash
command -v mpv          # should print a path
sudo apt install mpv    # Debian/Ubuntu — or `brew install mpv`, etc.
```

## Thumbnails don't appear

- **Plain terminal** — in non-graphics terminals, `textual-image` falls back to
  colored unicode blocks; the thumbnail looks blocky but should still appear. For
  sharp images use kitty/Ghostty/WezTerm (kitty graphics) or a sixel terminal.
- **No network** — thumbnails come from `i.ytimg.com` over HTTPS. If the fetch
  fails, BoxTube silently keeps the neutral placeholder; the rest of the UI works.
- **Verify fetching works**:

  ```bash
  .venv/bin/python -c "from boxtube import thumbnails; print(thumbnails.fetch('dQw4w9WgXcQ','https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg').size)"
  ```

## Personalized tabs are empty or fail (History, Liked, etc.)

The Library tabs need a valid YouTube cookies file.

- **Still shows "Sign in required"** — BoxTube can't find a non-empty cookies file.
  Check the path:

  ```bash
  .venv/bin/python -c "from boxtube import account; print(account.cookies_path(), account.is_signed_in())"
  ```

  Put your exported `cookies.txt` there (or set `BOXTUBE_COOKIES`), then press `r`.
- **Was working, now errors** — cookies expire. Re-export `cookies.txt` from your
  browser and overwrite the file. See the [accounts guide](accounts.md).
- **A tab loads but is empty** — that list may genuinely be empty (e.g. no Watch
  Later items), or your account region/settings hide it. Try another tab to
  confirm sign-in works.

## Video is blocky / low quality

You're on the `tct` (truecolor text) output, the universal fallback. This is
expected in non-graphics terminals. For photographic video:

- Run BoxTube in **kitty, Ghostty, or WezTerm** (auto-selects `kitty`), or
- Use a **sixel** terminal, or force it: `BOXTUBE_VO=sixel boxtube`.

See [configuration → video output](configuration.md#video-output-boxtube_vo).

## No audio (often under WSL)

Video plays but there's no sound — usually a missing PulseAudio/WSLg audio bridge,
not a BoxTube problem. Video playback is unaffected. Verify your system audio
(e.g. `mpv` a local file) outside BoxTube.

## Wrong video output is chosen

Auto-detection guessed wrong for your terminal. Override it:

```bash
BOXTUBE_VO=kitty boxtube     # or sixel / tct
```

If your terminal *should* be detected automatically but isn't, that's a bug worth
reporting — include `echo "$TERM $TERM_PROGRAM $KITTY_WINDOW_ID $WEZTERM_PANE"`.

## Search returns nothing / errors

- **No results** — try a simpler query; transient YouTube/`yt-dlp` hiccups happen.
- **An error toast appears** — the message comes from `yt-dlp`. Update it
  (see the first section) and retry.
- **Manual check**:

  ```bash
  .venv/bin/python -c "from boxtube.youtube import search; print(len(search('lofi', 3)))"
  ```

## `boxtube: command not found`

The console command isn't on your `PATH`.

```bash
ls -l ~/.local/bin/boxtube                       # exists?
ln -sf "$PWD/.venv/bin/boxtube" ~/.local/bin/boxtube   # (re)create it
echo "$PATH" | tr ':' '\n' | grep "$HOME/.local/bin"   # on PATH?
```

If `~/.local/bin` isn't on your `PATH`, add it (see
[installation](installation.md#putting-boxtube-on-your-path)).

## After moving the BoxTube folder, nothing works

The venv and symlink use **absolute paths**. Recreate them:

```bash
rm -rf .venv
make install link        # or the manual venv + pip + ln steps
```

## The UI looks broken (boxes / missing borders)

If panel borders show as `□` "tofu", your terminal font lacks box-drawing glyphs.
Use a font with good Unicode coverage (most programming fonts qualify). Note: this
is purely a font issue, not BoxTube — screenshots converted to PNG can show the
same artifact even when the live terminal renders correctly.
