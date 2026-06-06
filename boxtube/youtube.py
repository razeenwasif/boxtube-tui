"""YouTube search backed by the system ``yt-dlp`` binary.

No API key required. Searches run ``yt-dlp`` with a flat playlist dump so we
get one JSON object per result without resolving every stream URL up front.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


class SearchError(Exception):
    """Raised when a search cannot be completed."""


@dataclass
class Video:
    """A single search result."""

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


def search(query: str, limit: int = 20) -> list[Video]:
    """Search YouTube and return up to ``limit`` results.

    Runs synchronously; call from a worker thread to keep the UI responsive.
    """
    query = query.strip()
    if not query:
        return []

    cmd = [
        ytdlp_path(),
        f"ytsearch{limit}:{query}",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--ignore-errors",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if not proc.stdout.strip():
        message = proc.stderr.strip() or "yt-dlp returned no results."
        raise SearchError(message.splitlines()[-1] if message else "No results.")

    videos: list[Video] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("_type") == "playlist":
            continue
        vid = data.get("id")
        if not vid:
            continue
        videos.append(
            Video(
                id=vid,
                title=data.get("title") or "(no title)",
                channel=data.get("channel") or data.get("uploader") or "Unknown channel",
                duration=data.get("duration"),
                views=data.get("view_count"),
                description=data.get("description") or "",
            )
        )
    return videos
