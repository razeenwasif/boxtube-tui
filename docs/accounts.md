# Accounts & sign-in

BoxTube can show your personalized YouTube data — subscriptions feed, watch
history, liked videos, watch later, and playlists. This guide explains how
sign-in works and how to set it up.

## How sign-in works

There is **no username/password login**. YouTube blocks scripted password logins
(2FA, bot checks, ToS), and yt-dlp dropped password auth. Instead, BoxTube reads a
**cookies file** exported from a browser where you're already logged into
YouTube — the same mechanism yt-dlp uses for authenticated access.

- BoxTube looks for cookies at **`~/.config/boxtube/cookies.txt`**
  (or `$XDG_CONFIG_HOME/boxtube/cookies.txt`).
- Override the path with the **`BOXTUBE_COOKIES`** environment variable.
- "Signed in" simply means that file exists and is non-empty.

Search works **without** signing in.

## Setup (recommended: cookies.txt)

This method works everywhere, including **WSL** where your browser runs on Windows.

1. Install the
   **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)**
   extension (Chrome/Edge/Firefox variants exist).
2. Open a **private / incognito window**, log into YouTube there, and open a new
   tab on <https://www.youtube.com>.
3. Click the extension and **Export** (Netscape format). It downloads a
   `cookies.txt` (or `youtube.com_cookies.txt`).

> **Use a private window and close it right after exporting.** Browsers
> continuously rotate YouTube's session cookies; cookies exported from a window
> you keep browsing in are often invalidated within minutes, which makes BoxTube
> show empty feeds and "playlist does not exist" errors. A private window you
> close immediately keeps the exported session valid. Make sure you're **fully
> logged in** (you can see your avatar) before exporting.
4. Move it to the expected path:

   ```bash
   mkdir -p ~/.config/boxtube
   mv ~/Downloads/*cookies.txt ~/.config/boxtube/cookies.txt
   ```

   On WSL, if the download landed on the Windows side:

   ```bash
   mkdir -p ~/.config/boxtube
   cp /mnt/c/Users/<you>/Downloads/youtube.com_cookies.txt ~/.config/boxtube/cookies.txt
   ```
5. Launch BoxTube (or press **`r`** to refresh). The app bar shows **● Signed in**.

> Press **`?`** in BoxTube at any time to see these steps with your exact cookies
> path.

## Alternative: cookies from a Linux browser

If you have a **Linux** browser logged into YouTube, you can export from it the
same way. (BoxTube uses a cookies *file*; it does not read browser profiles
directly. Under WSL, a Windows browser profile is not readable — use the export
method above.)

## What each tab shows

| Tab | Source | Needs sign-in |
|-----|--------|---------------|
| 🏠 Home | Your subscriptions feed (latest uploads) | Yes |
| 🕘 History | Your watch history | Yes |
| 👍 Liked | Your liked videos (`LL`) | Yes |
| ⏰ Watch Later | Your watch later list (`WL`) | Yes |
| 🎵 Playlists | Your playlists → open one to see its videos | Yes |
| ◍ Subscriptions | Your subscribed channels → open one to see its videos | Yes |
| 🔍 Search / chips | Public YouTube search | No |

> **Why is there no algorithmic "Home" recommendations feed?** YouTube doesn't
> expose the recommendation feed to yt-dlp (and the official Data API exposes
> neither recommendations nor watch history). BoxTube's Home is your
> subscriptions feed, which is the closest reliable equivalent.

## Symptoms of bad cookies

If you're "signed in" but tabs are empty or error out, the cookies aren't
authenticating. Tell-tale signs:

- **Home / History show "This feed came back empty."**
- **Liked / Watch Later report "playlist does not exist".**

Both mean YouTube didn't accept the cookies — re-export them with the private
window method above. (Technically: a valid export includes the first-party login
cookies such as `SID`, `SAPISID`, `__Secure-1PSID`, and `LOGIN_INFO`; an export
missing those won't authenticate.) BoxTube shows these re-export steps in-app when
it detects the problem.

## Updating or signing out

- **Cookies expire.** If personalized tabs start failing, re-export `cookies.txt`
  (private window) and overwrite the file, then press `r`.
- **Sign out** by deleting the file:

  ```bash
  rm ~/.config/boxtube/cookies.txt
  ```

## Security & privacy

- Your cookies grant access to your YouTube account. Treat `cookies.txt` like a
  password: keep it readable only by you (`chmod 600 ~/.config/boxtube/cookies.txt`).
- BoxTube stores nothing else and sends your cookies only to YouTube (via yt-dlp
  and mpv). See the [security policy](../SECURITY.md).
