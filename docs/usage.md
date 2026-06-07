# Usage

A guide to BoxTube's interface and workflows.

## Launching

```bash
boxtube
```

If you're signed in, BoxTube opens on **Home** (your subscriptions feed). If not,
it shows sign-in steps and focuses the search box — search works either way. See
the [accounts guide](accounts.md) to enable personalized tabs.

## Interface tour

```
●  BoxTube                                          ● Signed in           ← app bar + auth
╭─ Search ───────────────────────────────────────────────────────────╮
│ your query here                                                     │   ← search (top bar)
╰─────────────────────────────────────────────────────────────────────╯
╭─ Library ──╮╭─ Home — Subscriptions (40) ─╮╭─ Preview ──────────────╮
│▌🏠 Home    ││▌Highlighted video title     ││      [ thumbnail ]     │
│ 🕘 History ││ Channel   12:34   1.2M      ││                        │
│ 👍 Liked   ││ Next video title            ││ Highlighted title      │
│ ⏰ Later   ││ Channel   3:21    44K       ││ Channel  …             │
│ 🎵 Playlist││ …                           ││ Length   …             │
╰────────────╯╰─────────────────────────────╯╰────────────────────────╯
 / Search   Enter Play   o Open   r Refresh   ? Sign in        ^q Quit     ← footer
```

- **App bar** — branding and your sign-in status (`● Signed in` / `○ Signed out`).
- **Search** — type a query, press **Enter** (works without signing in).
- **Library nav** — switch the middle pane between Home, History, Liked, Watch
  Later, and Playlists.
- **Results** — videos (or playlists) for the current tab. The highlighted row has
  a light-red accent bar.
- **Preview** — the highlighted video's thumbnail, metadata, and description.
- **Footer** — context keybindings.

## Keybindings

| Key | Action |
|-----|--------|
| `/` or `Esc` | Focus the search box |
| `Enter` | Run search (in box) / play video / open playlist (in results) |
| `↑` / `↓` | Move through the current list |
| `1`–`5` | Jump to a Library tab (Home, History, Liked, Watch Later, Playlists) |
| `p` | Play the highlighted video |
| `o` | Open the highlighted video in your web browser |
| `r` | Refresh the current tab (also re-checks sign-in) |
| `Backspace` | Go back from a playlist to the playlist list |
| `?` | Show sign-in steps |
| `Ctrl+Q` / `Ctrl+C` | Quit |

You can also click nav items and results with the mouse.

## Workflows

### Browse your feed (signed in)

1. Use the Library nav (click, `↑/↓` + `Enter`, or number keys `1`–`5`).
2. **Home** shows your subscriptions feed; **History**, **Liked**, and **Watch
   Later** show those lists.
3. Move through results with `↑/↓`; the preview updates as you go.

If you're signed out and open a personalized tab, BoxTube shows sign-in steps —
press `?` any time for them, and `r` to refresh once you've added cookies.

### Playlists (drill-down)

1. Open the **Playlists** tab (`5`). It lists your playlists.
2. Highlight one and press **Enter** to open it — the results switch to that
   playlist's videos.
3. Press **Backspace** to return to the playlist list.

### Search

1. Press `/` (or just type — it's focused when signed out).
2. Enter a query and press **Enter**. Results replace the current tab's list.

### Watch in the terminal

1. Highlight a video and press **Enter** (or `p`).
2. BoxTube opens its **custom player**: the video renders in the terminal with a
   control bar you can click. mpv runs in the background as the A/V engine.
3. Press **`q`** (or click **✕**) to close and return.

The control bar is fully mouse-driven, with keyboard shortcuts too:

| Control | Mouse | Key |
|---------|-------|-----|
| Play / pause | click ▶/⏸ | `Space` |
| Skip back / forward 5s | click ⏮ / ⏭ | `←` / `→` |
| Seek to a position | click anywhere on the seek bar | — |
| Volume | click on the volume bar | `↑` / `↓` |
| Close | click ✕ | `q` / `Esc` |

The video plays at ≤480p and is rendered with your terminal's graphics protocol
(kitty / sixel) or a unicode fallback — see
[configuration → video output](configuration.md#video-output-boxtube_vo).
Age-restricted videos play without sign-in; for private/members-only videos see
[`BOXTUBE_PLAYBACK_COOKIES`](configuration.md#playback-cookies-boxtube_playback_cookies).

### Open in a browser

Press `o` to open the highlighted video in your default web browser — handy for
full resolution.

## Tips

- Thumbnails are cached per video for the session, so re-visiting is instant.
- Playback caps streams at ≤480p — terminal cells are coarse, so lower
  resolutions start faster and look identical once rendered.
- For the sharpest experience, run BoxTube in a kitty-graphics terminal
  (kitty, Ghostty, WezTerm).
