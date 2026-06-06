"""Open URLs in the user's web browser, with WSL support.

On WSL there is usually no Linux browser, so ``xdg-open`` fails. We route to the
Windows browser via ``wslview`` (from wslu) or ``cmd.exe start`` instead, and fall
back to the standard :mod:`webbrowser` module everywhere else.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser


def is_wsl() -> bool:
    """True when running under the Windows Subsystem for Linux."""
    try:
        if "microsoft" in os.uname().release.lower():
            return True
    except AttributeError:
        pass
    try:
        with open("/proc/version") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _wslview(url: str) -> bool:
    exe = shutil.which("wslview")
    if not exe:
        return False
    try:
        subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def _windows_start(url: str) -> bool:
    exe = shutil.which("cmd.exe") or "/mnt/c/Windows/System32/cmd.exe"
    try:
        # Run from a Windows-accessible cwd so cmd.exe doesn't warn about the
        # WSL (UNC) working directory. The empty "" is start's window-title arg.
        subprocess.Popen(
            [exe, "/c", "start", "", url],
            cwd="/mnt/c",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def open_url(url: str) -> bool:
    """Open ``url`` in a browser. Returns True if an opener was launched."""
    if is_wsl():
        for opener in (_wslview, _windows_start):
            if opener(url):
                return True
    try:
        return webbrowser.open(url)
    except Exception:
        return False
