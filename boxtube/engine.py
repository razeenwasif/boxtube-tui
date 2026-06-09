"""Headless mpv playback engine, controlled over the JSON IPC socket.

mpv decodes audio + video and keeps the master clock; BoxTube drives it via IPC
(play/pause, seek, volume) and samples the *current* video frame on demand with
``screenshot-to-file`` — so the frames we render are always in sync with the
audio without a second decoder.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time

from .player import detect_hwdec
from .youtube import find_js_runtime, find_ytdlp


class EngineError(Exception):
    """Raised when mpv can't start or load the stream."""


def _screenshot_format() -> str:
    """Frame image format: ``jpg`` (fast, default) or ``png`` (lossless, sharper)."""
    fmt = os.environ.get("BOXTUBE_SCREENSHOT_FORMAT", "jpg").strip().lower()
    return "png" if fmt == "png" else "jpg"


def _screenshot_quality() -> int:
    """JPEG quality for sampled frames (1-100). Higher = fewer artifacts."""
    try:
        return max(1, min(100, int(os.environ.get("BOXTUBE_SCREENSHOT_QUALITY", "92"))))
    except ValueError:
        return 92


class MpvEngine:
    def __init__(self, url: str, *, cookies: str | None = None, max_height: int = 480) -> None:
        self.url = url
        self.cookies = cookies
        self.max_height = max_height
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._buf = b""
        self._rid = 0
        self._dir = tempfile.mkdtemp(prefix="boxtube-mpv-")
        self._sock_path = os.path.join(self._dir, "mpv.sock")
        # screenshot-to-file infers the format from the filename extension.
        self._frame_path = os.path.join(self._dir, f"frame.{_screenshot_format()}")
        self._err_path = os.path.join(self._dir, "mpv.err")
        self._err = None

    # ----- lifecycle -----------------------------------------------------

    def _build_command(self) -> list[str]:
        fmt = (
            f"bestvideo[height<={self.max_height}]+bestaudio/"
            f"best[height<={self.max_height}]/bestvideo+bestaudio/best"
        )
        cmd = [
            shutil.which("mpv") or "mpv",
            "--no-terminal",
            "--idle=no",
            "--force-window=no",
            "--vo=null",
            "--msg-level=all=error",
            f"--input-ipc-server={self._sock_path}",
            f"--screenshot-format={_screenshot_format()}",
            f"--screenshot-jpeg-quality={_screenshot_quality()}",
            f"--ytdl-format={fmt}",
            "--ytdl-raw-options-append=extractor-args=youtube:player_client=default,android_vr,tv",
        ]
        hwdec = detect_hwdec()
        if hwdec:
            cmd.append(f"--hwdec={hwdec}")
        ytdl = find_ytdlp()
        if ytdl:
            cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl}")
        js = find_js_runtime()
        if js:
            cmd.append(f"--ytdl-raw-options-append=js-runtimes={js}")
        if self.cookies:
            cmd.append(f"--ytdl-raw-options-append=cookies={self.cookies}")
        cmd.append(self.url)
        return cmd

    def start(self, timeout: float = 30.0) -> None:
        """Launch mpv and block until the stream is loaded. Raises EngineError."""
        self._err = open(self._err_path, "w")
        self._proc = subprocess.Popen(
            self._build_command(), stdout=subprocess.DEVNULL, stderr=self._err
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(self._sock_path):
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(self._sock_path)
                    self._sock = s
                    break
                except OSError:
                    pass
            if self._proc.poll() is not None:
                raise EngineError(self._read_err() or "mpv exited during startup.")
            time.sleep(0.1)
        if self._sock is None:
            raise EngineError("mpv IPC socket did not appear.")

        # Wait for the stream to load (duration becomes available).
        while time.time() < deadline:
            dur = self.get("duration")
            if isinstance(dur, (int, float)) and dur > 0:
                return
            if self._proc.poll() is not None:
                raise EngineError(self._read_err() or "mpv exited before loading the video.")
            time.sleep(0.2)
        raise EngineError(self._read_err() or "Timed out loading the video.")

    def _read_err(self) -> str:
        try:
            if self._err:
                self._err.flush()
            with open(self._err_path) as fh:
                lines = [ln.strip() for ln in fh if ln.strip()]
            for ln in reversed(lines):
                if "error" in ln.lower():
                    return ln.split("ERROR:", 1)[-1].strip() or ln
            return lines[-1] if lines else ""
        except OSError:
            return ""

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def quit(self) -> None:
        with self._lock:
            try:
                if self._sock:
                    self._sock.sendall(b'{"command":["quit"]}\n')
            except OSError:
                pass
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        except Exception:
            pass
        for closer in (lambda: self._sock and self._sock.close(), lambda: self._err and self._err.close()):
            try:
                closer()
            except Exception:
                pass
        shutil.rmtree(self._dir, ignore_errors=True)

    # ----- IPC -----------------------------------------------------------

    def _readline(self) -> str | None:
        while b"\n" not in self._buf:
            try:
                chunk = self._sock.recv(65536)
            except OSError:
                return None
            if not chunk:
                return None
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line.decode("utf-8", "replace")

    def _request(self, *args) -> dict | None:
        with self._lock:
            if self._sock is None:
                return None
            self._rid += 1
            rid = self._rid
            try:
                self._sock.sendall((json.dumps({"command": list(args), "request_id": rid}) + "\n").encode())
            except OSError:
                return None
            deadline = time.time() + 5
            while time.time() < deadline:
                line = self._readline()
                if line is None:
                    return None
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("request_id") == rid:  # skip async events
                    return msg
            return None

    def get(self, prop: str):
        msg = self._request("get_property", prop)
        return msg.get("data") if msg and msg.get("error") == "success" else None

    def set(self, prop: str, value) -> None:
        self._request("set_property", prop, value)

    def command(self, *args) -> None:
        self._request(*args)

    # ----- high-level controls ------------------------------------------

    def toggle_pause(self) -> None:
        self.command("cycle", "pause")

    def seek(self, seconds: float, mode: str = "relative") -> None:
        self.command("seek", seconds, mode)

    def seek_percent(self, fraction: float) -> None:
        self.command("seek", max(0.0, min(100.0, fraction * 100)), "absolute-percent")

    def set_volume(self, value: float) -> None:
        self.set("volume", max(0.0, min(130.0, value)))

    def screenshot(self) -> str:
        """Write the current video frame and return its path (blocks until written)."""
        self.command("screenshot-to-file", self._frame_path, "video")
        return self._frame_path
