"""Account / sign-in state, backed by a yt-dlp cookies file.

BoxTube "signs in" by reading a Netscape-format ``cookies.txt`` exported from a
browser where you're logged into YouTube — there is no password handling. This is
the same mechanism yt-dlp uses for authenticated access.

Default location: ``~/.config/boxtube/cookies.txt`` (or ``$XDG_CONFIG_HOME``).
Override the path with the ``BOXTUBE_COOKIES`` environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "boxtube"


def config_dir() -> Path:
    """The BoxTube configuration directory (created lazily by callers)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / APP_NAME


def cookies_path() -> Path:
    """Where the cookies file is expected. ``BOXTUBE_COOKIES`` overrides it."""
    override = os.environ.get("BOXTUBE_COOKIES")
    if override:
        return Path(override).expanduser()
    return config_dir() / "cookies.txt"


def is_signed_in() -> bool:
    """True when a non-empty cookies file is present."""
    path = cookies_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def cookies_arg() -> str | None:
    """The cookies path to pass to yt-dlp/mpv, or ``None`` when signed out."""
    return str(cookies_path()) if is_signed_in() else None
