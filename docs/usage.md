# Usage

A guide to BoxTube's interface and workflows.

## Launching

```bash
boxtube
```

The search box is focused on startup — just start typing.

## Interface tour

```
●  BoxTube                                              press / to search   ← app bar
╭─ Search ─────────────────────────────────────────────────────────────╮
│ your query here                                                       │   ← search input
╰──────────────────────────────────────────────────────────────────────╯
╭─ Results (N) ────────────────╮╭─ Preview ───────────────────────────╮
│▌Highlighted video title      ││           [ thumbnail ]             │   ← preview pane
│ Channel   12:34   1.2M views ││                                     │
│ Next video title             ││ Highlighted video title             │
│ Channel   3:21    44K views  ││ Channel   …                         │
│ …                            ││ Length    …                         │
│   (results list, scrolls)    ││ Views     …                         │
│                              ││ Link      <id>                      │
╰──────────────────────────────╯╰─ description … ─────────────────────╯
 / Search   Enter Play   o Open in browser                    ^q Quit      ← footer
```

- **App bar** — branding and a hint.
- **Search** — type a query and press **Enter**.
- **Results** — one row per video: title, channel, duration, view count. The
  highlighted row has a light-red accent bar.
- **Preview** — the highlighted video's thumbnail, then its metadata and
  description. The thumbnail scales with the window and keeps its 16:9 ratio.
- **Footer** — context keybindings.

## Keybindings

| Key | Action | Available |
|-----|--------|-----------|
| `/` | Focus the search box | Anywhere |
| `Esc` | Focus the search box | Anywhere |
| `Enter` | Run search (in search box) / play (in results) | Context-sensitive |
| `↑` / `↓` | Move through results | Results list |
| `p` | Play the highlighted video | Anywhere |
| `o` | Open the highlighted video in your web browser | Anywhere |
| `Ctrl+Q` / `Ctrl+C` | Quit | Anywhere |

## Workflows

### Search and browse

1. Press `/` (or just type — it's focused at startup).
2. Enter a query and press **Enter**. The results title shows `Searching…`, then
   `Results (N)`.
3. Use `↑`/`↓` to move through results. The preview pane updates as you move,
   loading each thumbnail in the background.

Searches return up to 25 results.

### Watch in the terminal

1. Highlight a video.
2. Press **Enter** (or `p`).
3. BoxTube suspends, prints the title and controls, and hands the terminal to
   mpv, which streams the video **inside the terminal**.
4. Press `q` in mpv to stop and return to BoxTube.

While mpv is playing:

| Key | Action |
|-----|--------|
| `q` | Quit playback, return to BoxTube |
| `Space` | Pause / resume |
| `←` / `→` | Seek backward / forward |
| `9` / `0` | Volume down / up |
| `f` | Fullscreen (graphics terminals) |

Rendering quality depends on your terminal — see
[Configuration → video output](configuration.md#video-output-boxtube_vo).

### Open in a browser

Press `o` to open the highlighted video at
`https://www.youtube.com/watch?v=<id>` in your default web browser. Useful when
you want full resolution or to keep it open while you keep browsing.

## Tips

- Thumbnails are cached per video for the session, so re-visiting a result is
  instant.
- Playback caps streams at ≤480p — terminal cells are coarse, so lower
  resolutions start faster and look identical once rendered.
- For the sharpest experience, run BoxTube in a kitty-graphics terminal
  (kitty, Ghostty, WezTerm).
