"""YouTube data access backed by the ``yt-dlp`` binary.

Search needs no authentication. The personalized feeds (subscriptions, history,
liked, watch later, playlists) require a cookies file — see :mod:`boxtube.account`
— which is threaded through every call as the optional ``cookies`` argument.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


class SearchError(Exception):
    """Raised when a search or feed load cannot be completed."""


@dataclass
class Video:
    """A single video result."""

    id: str
    title: str
    channel: str
    duration: int | None
    views: int | None
    description: str = ""

    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"

    @property
    def thumbnail_url(self) -> str:
        # mqdefault is a clean 320x180 16:9 frame (no letterboxing).
        return f"https://i.ytimg.com/vi/{self.id}/mqdefault.jpg"

    @property
    def duration_str(self) -> str:
        return human_duration(self.duration)

    @property
    def views_str(self) -> str:
        return human_number(self.views)


@dataclass
class Playlist:
    """A playlist entry, used for drill-down navigation."""

    id: str
    title: str
    count: int | None = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/playlist?list={self.id}"

    @property
    def count_str(self) -> str:
        return f"{self.count} videos" if self.count else "playlist"


# Authenticated feed targets (all require a cookies file).
FEED_SUBSCRIPTIONS = "https://www.youtube.com/feed/subscriptions"
FEED_HISTORY = "https://www.youtube.com/feed/history"
FEED_PLAYLISTS = "https://www.youtube.com/feed/playlists"
PLAYLIST_LIKED = "https://www.youtube.com/playlist?list=LL"
PLAYLIST_WATCH_LATER = "https://www.youtube.com/playlist?list=WL"


def human_number(n: int | None) -> str:
    """Format a count like 1532000 as ``1.5M``."""
    if n is None:
        return "—"
    value = float(n)
    for unit in ("", "K", "M", "B"):
        if abs(value) < 1000:
            if unit == "":
                return f"{int(value)}"
            return f"{value:.1f}{unit}"
        value /= 1000
    return f"{value:.1f}T"


def human_duration(seconds: int | None) -> str:
    """Format seconds as ``M:SS`` or ``H:MM:SS``."""
    if not seconds:
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def find_ytdlp() -> str | None:
    """Locate a yt-dlp binary, preferring the one installed in our venv.

    YouTube changes its stream cipher often, so a current yt-dlp matters. We
    keep an up-to-date copy alongside the running interpreter (the project
    venv); prefer it over whatever stale system binary might be on PATH.
    """
    bindir = os.path.dirname(sys.executable)
    for name in ("yt-dlp", "yt-dlp.exe"):
        candidate = os.path.join(bindir, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("yt-dlp")


def ytdlp_path() -> str:
    exe = find_ytdlp()
    if not exe:
        raise SearchError("yt-dlp is not installed or not on PATH.")
    return exe


# Preferred order; deno is yt-dlp's best-supported runtime.
_JS_RUNTIMES = ("deno", "bun", "node", "qjs")


def find_js_runtime() -> str | None:
    """Return a JavaScript runtime spec for yt-dlp's ``--js-runtimes``, or None.

    Recent yt-dlp uses a JS runtime to solve YouTube's challenges and surface the
    full set of formats. We auto-detect a locally installed, *Linux-native*
    runtime (a Windows ``.exe`` under ``/mnt`` won't work as yt-dlp's runtime).

    Override with ``BOXTUBE_JS_RUNTIME`` — set it to a spec like ``deno`` or
    ``node:/opt/node/bin``, or to an empty value to disable auto-detection.
    """
    if "BOXTUBE_JS_RUNTIME" in os.environ:
        return os.environ["BOXTUBE_JS_RUNTIME"].strip() or None
    for name in _JS_RUNTIMES:
        path = shutil.which(name)
        if path and not path.startswith("/mnt/"):
            return name
    return None


# ----- internal runner ---------------------------------------------------


def _clean_error(stderr: str) -> str:
    """Extract a concise, user-facing message from yt-dlp's stderr."""
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if "ERROR" in ln:
            return ln.split("ERROR:", 1)[-1].strip() or ln
    return lines[-1] if lines else "yt-dlp returned no output."


def _entries(target: str, *, limit: int, cookies: str | None) -> list[dict]:
    """Run yt-dlp for ``target`` and return parsed flat-playlist JSON objects."""
    cmd = [ytdlp_path()]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd += [target, "--flat-playlist", "--dump-json", "--no-warnings", "--ignore-errors"]
    if not target.startswith("ytsearch"):
        cmd += ["--playlist-end", str(limit)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not proc.stdout.strip():
        raise SearchError(_clean_error(proc.stderr) if proc.stderr.strip() else "No results.")

    out: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _is_video_entry(d: dict) -> bool:
    return (
        d.get("_type") != "playlist"
        and d.get("ie_key") in (None, "Youtube")
        and bool(d.get("id"))
    )


def _is_playlist_entry(d: dict) -> bool:
    url = d.get("url") or ""
    pid = d.get("id") or ""
    return (
        d.get("ie_key") == "YoutubeTab"
        or d.get("_type") == "playlist"
        or "list=" in url
        or pid[:2] in ("PL", "LL", "FL", "UU", "OL", "RD")
    )


def _dicts_to_videos(dicts: list[dict]) -> list[Video]:
    videos: list[Video] = []
    for d in dicts:
        if not _is_video_entry(d):
            continue
        videos.append(
            Video(
                id=d["id"],
                title=d.get("title") or "(no title)",
                channel=d.get("channel") or d.get("uploader") or "Unknown channel",
                duration=d.get("duration"),
                views=d.get("view_count"),
                description=d.get("description") or "",
            )
        )
    return videos


def _dicts_to_playlists(dicts: list[dict]) -> list[Playlist]:
    playlists: list[Playlist] = []
    for d in dicts:
        if not _is_playlist_entry(d):
            continue
        pid = d.get("id")
        if not pid:
            continue
        playlists.append(
            Playlist(id=pid, title=d.get("title") or "(untitled playlist)", count=d.get("playlist_count"))
        )
    return playlists


# ----- public API --------------------------------------------------------


def search(query: str, limit: int = 25, cookies: str | None = None) -> list[Video]:
    """Search YouTube and return up to ``limit`` results. Runs synchronously."""
    query = query.strip()
    if not query:
        return []
    return _dicts_to_videos(_entries(f"ytsearch{limit}:{query}", limit=limit, cookies=cookies))


def subscriptions_feed(limit: int = 40, cookies: str | None = None) -> list[Video]:
    return _dicts_to_videos(_entries(FEED_SUBSCRIPTIONS, limit=limit, cookies=cookies))


def watch_history(limit: int = 40, cookies: str | None = None) -> list[Video]:
    return _dicts_to_videos(_entries(FEED_HISTORY, limit=limit, cookies=cookies))


def liked_videos(limit: int = 50, cookies: str | None = None) -> list[Video]:
    return _dicts_to_videos(_entries(PLAYLIST_LIKED, limit=limit, cookies=cookies))


def watch_later(limit: int = 50, cookies: str | None = None) -> list[Video]:
    return _dicts_to_videos(_entries(PLAYLIST_WATCH_LATER, limit=limit, cookies=cookies))


def user_playlists(limit: int = 60, cookies: str | None = None) -> list[Playlist]:
    return _dicts_to_playlists(_entries(FEED_PLAYLISTS, limit=limit, cookies=cookies))


def playlist_videos(playlist_id: str, limit: int = 60, cookies: str | None = None) -> list[Video]:
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    return _dicts_to_videos(_entries(url, limit=limit, cookies=cookies))


def videos_for_feed(key: str, *, limit: int, cookies: str | None) -> list[Video]:
    """Dispatch a nav key to the matching video feed loader."""
    loaders = {
        "home": subscriptions_feed,
        "subscriptions": subscriptions_feed,
        "history": watch_history,
        "liked": liked_videos,
        "watch_later": watch_later,
    }
    try:
        loader = loaders[key]
    except KeyError:
        raise ValueError(f"Unknown feed key: {key!r}")
    return loader(limit, cookies)
