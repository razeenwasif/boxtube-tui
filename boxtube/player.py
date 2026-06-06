"""Play YouTube videos *inside the terminal* using mpv.

mpv renders video straight into the terminal using one of several video
outputs. We pick the best one available:

* ``kitty``  — kitty graphics protocol (kitty, Ghostty, WezTerm). Sharp.
* ``sixel``  — sixel graphics (xterm -ti vt340, foot, mlterm, …).
* ``tct``    — truecolor text blocks. Works in any 24-bit terminal. Default.

Override at any time with the ``BOXTUBE_VO`` environment variable, e.g.
``BOXTUBE_VO=sixel boxtube``.

mpv resolves the YouTube stream itself via its bundled ytdl hook, which shells
out to ``yt-dlp``. We point it explicitly at the discovered yt-dlp binary so it
works regardless of how mpv was packaged.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .youtube import find_ytdlp


def detect_vo() -> str:
    """Choose an mpv video output for the current terminal."""
    override = os.environ.get("BOXTUBE_VO")
    if override:
        return override

    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "").lower()

    if os.environ.get("KITTY_WINDOW_ID") or "kitty" in term or term_program == "ghostty":
        return "kitty"
    if os.environ.get("WEZTERM_PANE"):
        return "kitty"
    if "sixel" in term or term == "foot" or "mlterm" in term:
        return "sixel"
    return "tct"


def mpv_path() -> str | None:
    return shutil.which("mpv")


def build_command(url: str, vo: str | None = None, cookies: str | None = None) -> list[str]:
    vo = vo or detect_vo()
    mpv = mpv_path() or "mpv"
    cmd = [
        mpv,
        f"--vo={vo}",
        "--really-quiet",
        "--msg-level=all=error",
        # Cap resolution: terminal cells are coarse, lower res streams start
        # faster and decode lighter while looking identical once rendered.
        "--ytdl-format=bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    ]

    ytdl = find_ytdlp()
    if ytdl:
        cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl}")

    # Pass cookies to yt-dlp's hook so private / age-restricted videos play.
    if cookies:
        cmd.append(f"--ytdl-raw-options-append=cookies={cookies}")

    if vo == "tct":
        # Software scaling profile keeps text-mode playback smooth.
        cmd.append("--profile=sw-fast")

    cmd.append(url)
    return cmd


def play(url: str, vo: str | None = None, cookies: str | None = None) -> int:
    """Play ``url`` in the terminal, blocking until mpv exits.

    Returns mpv's exit code. The caller is responsible for suspending any TUI
    so mpv has the terminal to itself.
    """
    if mpv_path() is None:
        raise FileNotFoundError("mpv is not installed or not on PATH.")
    proc = subprocess.run(build_command(url, vo, cookies))
    return proc.returncode
