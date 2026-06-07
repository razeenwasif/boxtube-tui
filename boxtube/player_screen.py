"""Full-screen custom video player: BoxTube renders the frames and the controls.

mpv runs headless (see :mod:`boxtube.engine`); this screen samples frames into an
`Image` widget and draws its own crisp, mouse-driven control bar (play/pause,
skip, a clickable seek bar, volume, time).
"""

from __future__ import annotations

import asyncio
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
from textual_image.widget import Image

from .engine import EngineError, MpvEngine
from .youtube import Video, human_duration

FRAME_FPS = 12
FRAME_MAX_WIDTH = 640


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
        Binding("q,escape", "close", "Close", show=True),
    ]

    def __init__(self, video: Video, cookies: str | None = None) -> None:
        super().__init__()
        self.video = video
        self.cookies = cookies
        self.engine: MpvEngine | None = None
        self._stop = False
        self._close_started = False
        self._pump_running = False
        self._duration = 0.0

    def compose(self) -> ComposeResult:
        yield Static(f"[b #ff8a8a]{self.video.title}[/]", id="pl-title", markup=True)
        with Center(id="pl-stage"):
            yield Image(_black_frame(), id="pl-video")
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
        self.query_one("#pl-title", Static).update(
            f"[b #ff8a8a]{_esc(self.video.title)}[/]  [#6f6f78]· loading…[/]"
        )
        # Plain daemon threads (not Textual workers): the app shutdown sequence
        # waits for workers to finish, which would deadlock against an infinite
        # frame pump. Daemon threads are not awaited and check self._stop.
        threading.Thread(target=self._start_engine, daemon=True).start()

    def on_unmount(self) -> None:
        # Safety net: stop the frame pump and mpv if the screen goes away by any
        # path other than action_close (e.g. app shutdown), so no thread lingers.
        self._stop_playback()

    def _stop_playback(self) -> None:
        """Stop the frame pump and mpv. Idempotent; safe from any context."""
        self._stop = True
        engine, self.engine = self.engine, None
        if engine:
            threading.Thread(target=engine.quit, daemon=True).start()

    # ----- engine lifecycle ---------------------------------------------

    def _start_engine(self) -> None:
        engine = MpvEngine(self.video.watch_url, cookies=self.cookies)
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
        self.query_one("#pl-title", Static).update(f"[b #ff8a8a]{_esc(self.video.title)}[/]")
        self.query_one("#pl-pause", Button).label = "⏸"
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        self._pump_running = True
        try:
            self._pump_loop()
        finally:
            self._pump_running = False

    def _pump_loop(self) -> None:
        period = 1.0 / FRAME_FPS
        while not self._stop and self.engine and self.engine.is_alive():
            t0 = time.time()
            try:
                path = self.engine.screenshot()
                img = PILImage.open(path)
                img.load()
                if img.width > FRAME_MAX_WIDTH:
                    h = int(FRAME_MAX_WIDTH * img.height / img.width)
                    img = img.resize((FRAME_MAX_WIDTH, h))
                self._safe_call(self._set_frame, img)
            except Exception:
                pass
            try:
                tp = self.engine.get("time-pos") or 0.0
                paused = bool(self.engine.get("pause"))
                vol = self.engine.get("volume")
                self._safe_call(self._update_controls, tp, paused, vol)
            except Exception:
                pass
            time.sleep(max(0.0, period - (time.time() - t0)))
        if not self._stop:
            self._safe_call(self._schedule_close)  # reached EOF

    def _safe_call(self, fn, *args) -> None:
        """Marshal a call onto the UI thread, ignoring a shutting-down app."""
        try:
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _set_frame(self, img: PILImage.Image) -> None:
        try:
            self.query_one("#pl-video", Image).image = img
        except Exception:
            pass

    def _update_controls(self, time_pos: float, paused: bool, volume) -> None:
        dur = self._duration or 1
        self.query_one("#pl-seek", ClickBar).set_fraction(time_pos / dur)
        self.query_one("#pl-time", Label).update(
            f"{human_duration(int(time_pos))} / {human_duration(int(self._duration))}"
        )
        self.query_one("#pl-pause", Button).label = "▶" if paused else "⏸"
        if volume is not None:
            self.query_one("#pl-vol", ClickBar).set_fraction(float(volume) / 130)

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
