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
▶ BoxTube            ╭──────── Search ────────╮              ◉ You        ← header
 [All] Shorts Music Gaming News Live Podcasts Learning Sports …           ← filter chips
╭ You ───────╮╭ Home — Subscriptions (40) ──╮╭─ Preview ──────────────╮
│ 🏠 Home    ││ ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓        ││     [ thumbnail ]      │
│ 🕘 History ││ Title…  Title…  Title…       ││                        │
│ 🎵 Playlists│ Chan…   Chan…   Chan…        ││ Highlighted title      │
│ ⏰ Later   ││ ▓▓▓▓▓   ▓▓▓▓▓   ▓▓▓▓▓        ││ Channel                │
│ 👍 Liked   ││ Title…  Title…  Title…       ││ 1.2M views · 12:34     │
│ Subscriptions                             ││ link · description     │
│ ◍ Lofi Girl││                             ││                        │
╰────────────╯╰─────────────────────────────╯╰────────────────────────╯
 / Search   Enter Play   o Open   r Refresh   ? Sign in        ^q Quit     ← footer
```

- **Header** — the ▶ BoxTube logo, a centered search bar (type + **Enter**; works
  signed out), and your sign-in status on the right (`◉ You` / `○ Sign in`).
- **Filter chips** — click a category pill to search it; **All** returns to Home;
  **Shorts** loads a feed of YouTube Shorts from your subscribed channels.
- **Sidebar** — a **You** group (Home, History, Playlists, Watch Later, Liked) and
  a **Subscriptions** group listing your subscribed channels.
- **Grid** — a responsive grid of video cards (thumbnail + title + channel · views
  · duration). The highlighted card has a red border. Move with the **arrow
  keys**; press **Enter** to play (or double-click a card).
- **Preview** — the highlighted video's larger thumbnail, title, channel,
  views/length, link, and description.
- **Footer** — context keybindings.

## Keybindings

| Key | Action |
|-----|--------|
| `/` or `Esc` | Focus the search box |
| `Enter` | Run search (in box) / play the highlighted video / open a playlist |
| `↑` `↓` `←` `→` | Move through the video grid |
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

### Subscribed channels & filter chips

- The **Subscriptions** group in the sidebar lists your subscribed channels.
  Click one (or focus the list and press **Enter**) to load that channel's
  videos; **Backspace** goes back.
- The **filter chips** under the header run a search for that category (e.g.
  *Music*, *Gaming*). **All** returns to your Home feed. **Shorts** loads a feed
  of YouTube Shorts gathered from the **Shorts tabs of the channels you're
  subscribed to** (interleaved so no single channel dominates). When signed out
  it falls back to the public `#shorts` hashtag. Shorts play in the normal
  player; being vertical, they appear pillarboxed (bars left and right).

### Playlists (drill-down)

1. Open the **Playlists** tab (`3`). It lists your playlists.
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

The video plays at ≤360p (tunable via `BOXTUBE_PLAYER_HEIGHT`) and is rendered
on a steady timer (`BOXTUBE_PLAYER_FPS`) with your terminal's graphics protocol
(kitty / sixel) or a unicode fallback — see
[configuration → video output](configuration.md#video-output-boxtube_vo).
Age-restricted videos play without sign-in; for private/members-only videos see
[`BOXTUBE_PLAYBACK_COOKIES`](configuration.md#playback-cookies-boxtube_playback_cookies).

### Open in a browser

Press `o` to open the highlighted video in your default web browser — handy for
full resolution.

## Tips

- Thumbnails are cached per video for the session, so re-visiting is instant.
- The player streams at ≤360p by default — terminal cells are coarse, so lower
  resolutions start faster and decode lighter. Tune with `BOXTUBE_PLAYER_HEIGHT`
  / `BOXTUBE_PLAYER_FPS` (see [configuration](configuration.md#player-performance-boxtube_player_fps-boxtube_player_height)).
- For the sharpest experience, run BoxTube in a kitty-graphics terminal
  (kitty, Ghostty, WezTerm).
