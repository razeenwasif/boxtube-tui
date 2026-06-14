"""Per-video watch progress, persisted as JSON.

Remembers how far into each video you watched so reopening it resumes where you
left off (YouTube-style). Stored next to the config file — in
``~/.config/boxtube/watch_progress.json`` by default (override the file with
``BOXTUBE_PROGRESS``, or move the whole dir with ``BOXTUBE_CONFIG``).

The player records the current position periodically and on close, and clears an
entry once a video is watched to the end. :func:`resume_at` returns a meaningful
resume point (or ``None``) for a given video.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import config

# Don't bother resuming the first few seconds — that's effectively "from the
# start" and just gets in the way.
MIN_RESUME_SECONDS = 15
# Treat a video as finished (so we don't resume at the very end next time) when
# the position is within this many seconds of the end, or this far through.
END_MARGIN_SECONDS = 20
END_FRACTION = 0.97
# Cap the file: keep this many most-recently-watched entries.
MAX_ENTRIES = 500

_LOCK = threading.Lock()


def progress_path() -> Path:
    override = os.environ.get("BOXTUBE_PROGRESS")
    if override:
        return Path(override).expanduser()
    return config.config_path().parent / "watch_progress.json"


def _is_finished(position: float, duration: float) -> bool:
    if duration <= 0:
        return False
    return position >= duration - END_MARGIN_SECONDS or position >= duration * END_FRACTION


def _load_items() -> dict:
    try:
        with open(progress_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    items = raw.get("items") if isinstance(raw, dict) else None
    return items if isinstance(items, dict) else {}


def _save_items(items: dict) -> None:
    if len(items) > MAX_ENTRIES:
        ordered = sorted(items.items(), key=lambda kv: kv[1].get("updated", 0), reverse=True)
        items = dict(ordered[:MAX_ENTRIES])
    path = progress_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "items": items}), encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX


def load() -> dict:
    """Return the whole {video_id: record} mapping. Never raises."""
    with _LOCK:
        return _load_items()


def record(video_id: str, position: float, duration: float, title: str = "") -> None:
    """Store the watch position for a video.

    A position below :data:`MIN_RESUME_SECONDS` or past the end is not worth
    resuming, so any existing entry is dropped instead (keeps the file lean and
    means a re-watch from the top forgets a stale resume point).
    """
    if not video_id:
        return
    position = float(position)
    duration = float(duration)
    with _LOCK:
        items = _load_items()
        if position < MIN_RESUME_SECONDS or _is_finished(position, duration):
            if video_id in items:
                del items[video_id]
                _save_items(items)
            return
        items[video_id] = {
            "position": round(position, 1),
            "duration": round(duration, 1),
            "title": title,
            "updated": time.time(),
        }
        _save_items(items)


def clear(video_id: str) -> None:
    """Forget a video's saved position (e.g. once it's watched to the end)."""
    if not video_id:
        return
    with _LOCK:
        items = _load_items()
        if video_id in items:
            del items[video_id]
            _save_items(items)


def resume_at(video_id: str) -> float | None:
    """Return a meaningful resume position for ``video_id``, or ``None``."""
    if not video_id:
        return None
    with _LOCK:
        rec = _load_items().get(video_id)
    if not rec:
        return None
    pos = float(rec.get("position", 0))
    dur = float(rec.get("duration", 0))
    if pos < MIN_RESUME_SECONDS or _is_finished(pos, dur):
        return None
    return pos
