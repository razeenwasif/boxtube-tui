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

from .youtube import find_js_runtime, find_ytdlp


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
        # Quiet, but NOT --really-quiet: the latter suppresses errors too, which
        # hides playback failures. error level keeps the screen clean on success
        # while still surfacing real problems.
        "--msg-level=all=error",
        # Cap resolution: terminal cells are coarse, lower res streams start
        # faster and decode lighter while looking identical once rendered. The
        # final, uncapped fallback guarantees *something* plays.
        "--ytdl-format=bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo+bestaudio/best",
        # Force JS-free YouTube clients. Recent yt-dlp needs a JS runtime for the
        # default "web" client; without one it returns a degraded format set and
        # mpv's ytdl hook fails with "Requested format is not available". The
        # android_vr/tv clients need no JS and return full formats.
        "--ytdl-raw-options-append=extractor-args=youtube:player_client=default,android_vr,tv",
    ]

    ytdl = find_ytdlp()
    if ytdl:
        cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl}")

    # Enable a JS runtime when one is available so yt-dlp can extract the full
    # format set (complements the JS-free client fallback above).
    js = find_js_runtime()
    if js:
        cmd.append(f"--ytdl-raw-options-append=js-runtimes={js}")

    # Cookies are opt-in for playback: the JS-free android_vr/tv clients above
    # don't support authenticated requests, so cookies force the JS-dependent web
    # client and break extraction. Only pass them when explicitly enabled (and a
    # full JS solver is available). Age-restricted videos already work cookie-free
    # via the android_vr/tv clients. The caller decides whether to pass cookies.
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
