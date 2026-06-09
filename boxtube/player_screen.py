"""Full-screen custom video player: BoxTube renders the frames and the controls.

mpv runs headless (see :mod:`boxtube.engine`); this screen samples frames into an
`Image` widget and draws its own crisp, mouse-driven control bar (play/pause,
skip, a clickable seek bar, volume, time).
"""

from __future__ import annotations

import asyncio
import os
import threading
import time

from PIL import Image as PILImage
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static
from textual_image.widget import (
    HalfcellImage,
    SixelImage,
    TGPImage,
    UnicodeImage,
)
from textual_image.widget import Image as AutoResolvedImage

from .engine import EngineError, MpvEngine
from .youtube import Video, human_duration

def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


# Render/capture cadence and frame size. Capture runs independently and the UI
# renders the latest frame on a steady timer (stale frames are dropped), which
# smooths the jitter from mpv's variable screenshot latency.
PLAYER_FPS = _env_int("BOXTUBE_PLAYER_FPS", 15, 1, 60)
# Source resolution cap fed to mpv. Kept at 360p by default: mpv takes an
# on-demand screenshot every frame *inside its playback loop*, so a higher source
# makes each screenshot heavier and can stall audio — most painful on sixel
# terminals under WSL. Raise it on a fast graphics terminal (kitty/Ghostty).
PLAYER_HEIGHT = _env_int("BOXTUBE_PLAYER_HEIGHT", 360, 144, 1080)
# Upper bound on the pixel width we hand the image backend. Frames are sized to
# the video widget's on-screen pixel area, capped here. Sixel encode/transmit
# cost grows with pixel count, so the default stays modest; raise it (or the
# source height) on a cheap-transmit graphics terminal for sharper video.
MAX_DISPLAY_WIDTH = _env_int("BOXTUBE_PLAYER_MAXWIDTH", 480, 240, 3840)
DISPLAY_WIDTH_FALLBACK = 480


# ----- image backend selection / diagnostics ---------------------------------

# Force a specific backend with BOXTUBE_IMAGE_BACKEND (sixel/kitty/halfcell/…);
# otherwise textual-image auto-detects the best one the terminal supports.
_BACKENDS = {
    "sixel": SixelImage,
    "tgp": TGPImage,
    "kitty": TGPImage,
    "halfcell": HalfcellImage,
    "half": HalfcellImage,
    "unicode": UnicodeImage,
    "ascii": UnicodeImage,
}


def _player_image_class():
    forced = os.environ.get("BOXTUBE_IMAGE_BACKEND", "").strip().lower()
    # Default to textual-image's already-resolved widget. Crucially this is the
    # dedicated SixelImage on a sixel terminal — the generic AutoImage does NOT
    # paint sixel (the library special-cases it for exactly this reason), so
    # using AutoImage here renders a black screen.
    return _BACKENDS.get(forced, AutoResolvedImage)


# Resolve once at import; the widget class is stable for the session.
PlayerImage = _player_image_class()


def _active_backend() -> str:
    """Short name of the image backend actually in use (for the title bar)."""
    forced = os.environ.get("BOXTUBE_IMAGE_BACKEND", "").strip().lower()
    if forced in _BACKENDS:
        return forced
    try:
        import textual_image.renderable as _r

        return _r.Image.__module__.rsplit(".", 1)[-1]  # sixel / tgp / halfcell / unicode
    except Exception:
        return "auto"


def _cell_px_width() -> int:
    try:
        from textual_image._terminal import get_cell_size

        return get_cell_size().width or 10
    except Exception:
        return 10


def _black_frame() -> PILImage.Image:
    return PILImage.new("RGB", (640, 360), (0, 0, 0))


class ClickBar(Static):
    """A horizontal bar (progress / volume) that reports a fraction when clicked."""

    class Clicked(Message):
        def __init__(self, bar_id: str, fraction: float) -> None:
            super().__init__()
            self.bar_id = bar_id
            self.fraction = fraction

    def __init__(self, *, id: str) -> None:
        super().__init__(id=id)
        self._fraction = 0.0

    def set_fraction(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self.refresh()

    def render(self) -> Text:
        width = max(1, self.size.width)
        pos = int(self._fraction * (width - 1))
        text = Text()
        text.append("━" * pos, style="#ff6b6b")
        text.append("●", style="#ff8a8a")
        text.append("─" * (width - pos - 1), style="#3a3a44")
        return text

    def on_click(self, event) -> None:
        width = max(1, self.size.width - 1)
        self.post_message(self.Clicked(self.id or "", event.x / width))


class PlayerScreen(Screen):
    """Custom in-terminal video player."""

    BINDINGS = [
        Binding("space", "pause", "Play/Pause", show=True),
        Binding("left", "back", "-5s", show=True),
        Binding("right", "forward", "+5s", show=True),
        Binding("up", "vol_up", "Vol+", show=False),
        Binding("down", "vol_down", "Vol-", show=False),
        Binding("n", "next", "Next", show=True),
        Binding("b", "prev", "Prev", show=True),
        Binding("q,escape", "close", "Close", show=True),
    ]

    def __init__(
        self,
        video: Video,
        cookies: str | None = None,
        *,
        playlist: list[Video] | None = None,
        index: int = 0,
        autoplay: bool = False,
    ) -> None:
        super().__init__()
        self.video = video
        self.cookies = cookies
        # The feed this video came from, so we can advance to the next clip. When
        # autoplay is on (Shorts), reaching EOF rolls into the next item instead
        # of closing. n / b (and the end of a clip) move through the playlist.
        self.playlist = playlist if playlist else [video]
        self.index = index if 0 <= index < len(self.playlist) else 0
        self.autoplay = autoplay
        # Read settings fresh per playback so the Settings screen takes effect
        # on the next video without a restart.
        self._fps = _env_int("BOXTUBE_PLAYER_FPS", 15, 1, 60)
        self._height = _env_int("BOXTUBE_PLAYER_HEIGHT", 360, 144, 1080)
        self._maxw = _env_int("BOXTUBE_PLAYER_MAXWIDTH", 480, 240, 3840)
        self._image_cls = _player_image_class()
        self._backend = _active_backend()
        # Target frame width in pixels; recomputed from the widget's on-screen
        # size once the layout settles (see _recompute_target).
        self._target_w = min(self._maxw, DISPLAY_WIDTH_FALLBACK)
        self.engine: MpvEngine | None = None
        self._stop = False
        self._close_started = False
        self._switching = False
        self._pump_running = False
        self._duration = 0.0
        # Decoupled capture/render: the capture thread writes the latest frame
        # and properties here; the render timer (UI thread) picks them up.
        self._latest = None
        self._shown = None
        self._props: dict = {}
        self._render_timer = None

    def compose(self) -> ComposeResult:
        yield Static(f"[b #ff8a8a]{self.video.title}[/]", id="pl-title", markup=True)
        with Center(id="pl-stage"):
            yield self._image_cls(_black_frame(), id="pl-video")
        with Horizontal(id="pl-controls"):
            yield Button("⏮", id="pl-back")
            yield Button("▶", id="pl-pause")
            yield Button("⏭", id="pl-fwd")
            yield Label("0:00 / 0:00", id="pl-time")
            yield ClickBar(id="pl-seek")
            yield Label("🔊", id="pl-volicon")
            yield ClickBar(id="pl-vol")
            yield Button("✕", id="pl-close")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#pl-seek", ClickBar).set_fraction(0.0)
        self.query_one("#pl-vol", ClickBar).set_fraction(100 / 130)
        self._set_title(loading=True)
        # Plain daemon threads (not Textual workers): the app shutdown sequence
        # waits for workers to finish, which would deadlock against an infinite
        # frame pump. Daemon threads are not awaited and check self._stop.
        threading.Thread(target=self._start_engine, daemon=True).start()

    def on_unmount(self) -> None:
        # Safety net: stop the frame pump and mpv if the screen goes away by any
        # path other than action_close (e.g. app shutdown), so no thread lingers.
        self._stop_playback()

    def _stop_playback(self) -> None:
        """Stop the render timer, frame pump, and mpv. Idempotent; any context."""
        self._stop = True
        if self._render_timer is not None:
            try:
                self._render_timer.stop()
            except Exception:
                pass
            self._render_timer = None
        engine, self.engine = self.engine, None
        if engine:
            threading.Thread(target=engine.quit, daemon=True).start()

    # ----- engine lifecycle ---------------------------------------------

    def _start_engine(self) -> None:
        engine = MpvEngine(self.video.watch_url, cookies=self.cookies, max_height=self._height)
        try:
            engine.start()
        except Exception as exc:
            self._safe_call(self._fail, str(exc))
            return
        if self._stop:
            engine.quit()
            return
        self.engine = engine
        self._safe_call(self._on_started)

    def _fail(self, message: str) -> None:
        self.notify(f"Playback failed: {message}", severity="error", timeout=8)
        self._schedule_close()

    def _on_started(self) -> None:
        if self._stop:
            return
        self._duration = float(self.engine.get("duration") or 0)
        self._set_title()
        self.query_one("#pl-pause", Button).label = "⏸"
        self._recompute_target()
        # Capture runs on a daemon thread; the UI renders the latest frame on a
        # steady Textual timer so cadence is even and slow frames are dropped.
        threading.Thread(target=self._capture, daemon=True).start()
        self._render_timer = self.set_interval(1.0 / self._fps, self._render_tick)

    def on_resize(self, event) -> None:
        self._recompute_target()

    def _recompute_target(self) -> None:
        """Size frames to the video widget's on-screen pixel area (UI thread).

        The image backend scales each frame to the widget's cell box, so matching
        that pixel width is the sharpest the terminal can show without sending
        more pixels than it can paint.
        """
        try:
            cells = self.query_one("#pl-video", self._image_cls).size.width
        except Exception:
            cells = 0
        if cells:
            self._target_w = max(160, min(self._maxw, cells * _cell_px_width()))

    def _capture(self) -> None:
        self._pump_running = True
        try:
            self._capture_loop()
        finally:
            self._pump_running = False

    def _capture_loop(self) -> None:
        period = 1.0 / self._fps
        while not self._stop and self.engine and self.engine.is_alive():
            t0 = time.time()
            paused = False
            try:
                paused = bool(self.engine.get("pause"))
                self._props = {
                    "time-pos": self.engine.get("time-pos") or 0.0,
                    "pause": paused,
                    "volume": self.engine.get("volume"),
                }
            except Exception:
                pass
            # A paused frame never changes — skip the screenshot + re-render.
            if not paused:
                try:
                    path = self.engine.screenshot()
                    img = PILImage.open(path)
                    img.load()
                    tw = self._target_w
                    # Only downscale (LANCZOS = sharp); never upscale — that adds
                    # no detail and only inflates the transmit cost. The backend
                    # upscales to the cell box if the frame is smaller.
                    if img.width > tw:
                        h = max(1, round(tw * img.height / img.width))
                        img = img.resize((tw, h), PILImage.LANCZOS)
                    self._latest = img  # atomic publish; render timer picks it up
                except Exception:
                    pass
            time.sleep(max(0.0, period - (time.time() - t0)))
        if not self._stop:
            self._safe_call(self._on_playback_ended)  # reached EOF

    def _render_tick(self) -> None:
        """Runs on the UI thread on a fixed interval; shows the latest frame."""
        img = self._latest
        if img is not None and img is not self._shown:
            self._shown = img
            try:
                self.query_one("#pl-video", self._image_cls).image = img
            except Exception:
                pass
        if self._props:
            self._apply_controls(self._props)

    def _apply_controls(self, props: dict) -> None:
        dur = self._duration or 1
        time_pos = props.get("time-pos") or 0.0
        self.query_one("#pl-seek", ClickBar).set_fraction(time_pos / dur)
        self.query_one("#pl-time", Label).update(
            f"{human_duration(int(time_pos))} / {human_duration(int(self._duration))}"
        )
        self.query_one("#pl-pause", Button).label = "▶" if props.get("pause") else "⏸"
        vol = props.get("volume")
        if vol is not None:
            self.query_one("#pl-vol", ClickBar).set_fraction(float(vol) / 130)

    def _safe_call(self, fn, *args) -> None:
        """Marshal a call onto the UI thread, ignoring a shutting-down app."""
        try:
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _set_title(self, *, loading: bool = False) -> None:
        pos = ""
        if len(self.playlist) > 1:
            pos = f"  [#6f6f78]· {self.index + 1}/{len(self.playlist)}[/]"
        suffix = "  [#6f6f78]· loading…[/]" if loading else f"  [#6f6f78]· {self._backend}[/]"
        try:
            self.query_one("#pl-title", Static).update(
                f"[b #ff8a8a]{_esc(self.video.title)}[/]{pos}{suffix}"
            )
        except Exception:
            pass

    # ----- playlist navigation ------------------------------------------

    def _on_playback_ended(self) -> None:
        """Called on natural EOF. Auto-advance when enabled, else close."""
        if self._close_started:
            return
        if self.autoplay and self.index + 1 < len(self.playlist):
            self._go(1)
        else:
            self._schedule_close()

    def _go(self, delta: int) -> None:
        """Move by ``delta`` within the playlist and play that clip in place."""
        if self._close_started or self._switching:
            return
        target = self.index + delta
        if not (0 <= target < len(self.playlist)):
            return  # at an end of the playlist; do nothing
        self.index = target
        try:
            asyncio.get_running_loop().create_task(self._switch_to(self.playlist[target]))
        except RuntimeError:
            pass

    async def _switch_to(self, video: Video) -> None:
        """Tear down the current clip and start the next one without leaving."""
        if self._close_started:
            return
        self._switching = True
        self._stop = True
        # Let the capture pump observe _stop and finish its current iteration.
        for _ in range(30):
            if not self._pump_running:
                break
            await asyncio.sleep(0.02)
        self._stop_playback()  # stops timer + quits old engine (sets _stop=True)
        # Reset per-clip state for the new video.
        self.video = video
        self._stop = False
        self._latest = None
        self._shown = None
        self._props = {}
        self._duration = 0.0
        try:
            self.query_one("#pl-video", self._image_cls).image = _black_frame()
            self.query_one("#pl-seek", ClickBar).set_fraction(0.0)
            self.query_one("#pl-time", Label).update("0:00 / 0:00")
            self.query_one("#pl-pause", Button).label = "▶"
        except Exception:
            pass
        self._set_title(loading=True)
        self._switching = False
        threading.Thread(target=self._start_engine, daemon=True).start()

    # ----- actions -------------------------------------------------------

    def action_pause(self) -> None:
        if self.engine:
            self.engine.toggle_pause()

    def action_back(self) -> None:
        if self.engine:
            self.engine.seek(-5)

    def action_forward(self) -> None:
        if self.engine:
            self.engine.seek(5)

    def action_vol_up(self) -> None:
        if self.engine:
            self.engine.set_volume((self.engine.get("volume") or 100) + 5)

    def action_vol_down(self) -> None:
        if self.engine:
            self.engine.set_volume((self.engine.get("volume") or 100) - 5)

    def action_next(self) -> None:
        self._go(1)

    def action_prev(self) -> None:
        self._go(-1)

    async def action_close(self) -> None:
        if self._close_started:
            return
        self._close_started = True
        self._stop = True
        # Let the frame pump observe _stop and finish its current iteration
        # before we pop, so it isn't mid-call_from_thread during teardown.
        for _ in range(30):
            if not self._pump_running:
                break
            await asyncio.sleep(0.02)
        self._stop_playback()
        # The pop must be awaited — an un-awaited pop_screen() leaves a pending
        # future that stalls app shutdown.
        try:
            await self.app.pop_screen()
        except Exception:
            pass

    def _schedule_close(self) -> None:
        """Request a close from a sync (UI-thread) callback."""
        if self._close_started:
            return
        try:
            asyncio.get_running_loop().create_task(self.action_close())
        except RuntimeError:
            pass

    # ----- events --------------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pl-close":
            await self.action_close()
            return
        action = {
            "pl-back": self.action_back,
            "pl-pause": self.action_pause,
            "pl-fwd": self.action_forward,
        }.get(event.button.id)
        if action:
            action()

    def on_click_bar_clicked(self, event: ClickBar.Clicked) -> None:
        if not self.engine:
            return
        if event.bar_id == "pl-seek":
            self.engine.seek_percent(event.fraction)
        elif event.bar_id == "pl-vol":
            self.engine.set_volume(event.fraction * 130)

def _esc(text: str) -> str:
    return text.replace("[", r"\[")
