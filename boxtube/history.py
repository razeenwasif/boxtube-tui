"""Recent search queries, persisted as JSON.

Powers the search bar's history-backed suggestions (inline completion of what
you've searched before). Stored next to the config file — in
``~/.config/boxtube/search_history.json`` by default (override the file with
``BOXTUBE_HISTORY``, or move the whole dir with ``BOXTUBE_CONFIG``).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from . import config

# Keep the most recent N distinct queries.
MAX_ITEMS = 50

_LOCK = threading.Lock()


def history_path() -> Path:
    override = os.environ.get("BOXTUBE_HISTORY")
    if override:
        return Path(override).expanduser()
    return config.config_path().parent / "search_history.json"


def _load_queries() -> list[str]:
    try:
        with open(history_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    queries = raw.get("queries") if isinstance(raw, dict) else None
    if not isinstance(queries, list):
        return []
    return [q for q in queries if isinstance(q, str)]


def _save_queries(queries: list[str]) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "queries": queries[:MAX_ITEMS]}), encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX


def recent() -> list[str]:
    """Return recent search queries, most-recent first. Never raises."""
    with _LOCK:
        return _load_queries()


def add(query: str) -> None:
    """Record a search query at the front, de-duplicated (case-insensitive)."""
    query = (query or "").strip()
    if not query:
        return
    with _LOCK:
        queries = _load_queries()
        lower = query.casefold()
        queries = [q for q in queries if q.casefold() != lower]
        queries.insert(0, query)
        _save_queries(queries)


def clear() -> None:
    """Forget all search history."""
    with _LOCK:
        _save_queries([])
