"""Tests for the custom player screen, using a fake engine (no mpv/network)."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
from PIL import Image as PILImage

from boxtube import player_screen
from boxtube.app import BoxTube
from boxtube.player_screen import ClickBar, PlayerScreen
from boxtube.youtube import Video


def run(coro):
    return asyncio.run(coro)


class FakeEngine:
    """Stand-in for MpvEngine: no process, canned properties, records calls."""

    def __init__(self, url, cookies=None, max_height=480):
        self.url = url
        self.cookies = cookies
        self.max_height = max_height
        self.calls: list = []
        self._t = 0.0
        self._paused = False
        self._vol = 100.0
        self._dur = 100.0
        d = tempfile.mkdtemp(prefix="boxtube-fake-")
        self._frame = os.path.join(d, "f.jpg")
        PILImage.new("RGB", (64, 36), (10, 20, 30)).save(self._frame)

    def start(self):
        self.calls.append("start")

    def is_alive(self):
        return True

    def get(self, prop):
        return {"duration": self._dur, "time-pos": self._t, "pause": self._paused, "volume": self._vol}.get(prop)

    def screenshot(self):
        self._t += 0.1
        return self._frame

    def toggle_pause(self):
        self._paused = not self._paused
        self.calls.append("pause")

    def seek(self, secs, mode="relative"):
        self.calls.append(("seek", secs))

    def seek_percent(self, frac):
        self.calls.append(("seek_percent", frac))

    def set_volume(self, value):
        self._vol = value
        self.calls.append(("vol", value))

    def quit(self):
        self.calls.append("quit")


# ----- ClickBar ----------------------------------------------------------


def test_clickbar_fraction_clamps():
    bar = ClickBar(id="b")
    bar.set_fraction(2.0)
    assert bar._fraction == 1.0
    bar.set_fraction(-1.0)
    assert bar._fraction == 0.0
    bar.set_fraction(0.5)
    assert bar._fraction == 0.5


# ----- PlayerScreen with a fake engine -----------------------------------


@pytest.fixture(autouse=True)
def _fake_engine(monkeypatch):
    monkeypatch.setattr(player_screen, "MpvEngine", FakeEngine)
    # Keep the host app offline so its startup feed-load doesn't hit the network
    # (which would otherwise stall app shutdown at the end of the test).
    monkeypatch.setattr("boxtube.account.is_signed_in", lambda: False)
    monkeypatch.setattr("boxtube.account.cookies_arg", lambda: None)
    monkeypatch.setattr("boxtube.thumbnails.fetch", lambda vid, url: PILImage.new("RGB", (320, 180)))


async def _open_player(app, video):
    app.push_screen(PlayerScreen(video))
    for _ in range(80):
        await asyncio.sleep(0.05)
        scr = app.screen
        if isinstance(scr, PlayerScreen) and scr.engine and scr._duration > 0:
            return scr
    raise AssertionError("player engine did not start")


def test_player_starts_and_renders():
    async def go():
        app = BoxTube()
        async with app.run_test(size=(100, 30)):
            scr = await _open_player(app, Video(id="x", title="T", channel="c", duration=100, views=1))
            assert scr._duration == 100.0
            # the frame pump set an image and updated the time label
            await asyncio.sleep(0.2)
            from textual_image.widget import Image
            assert scr.query_one("#pl-video", Image).image is not None

    run(go())


def test_controls_drive_engine():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            scr = await _open_player(app, Video(id="x", title="T", channel="c", duration=100, views=1))
            scr.action_pause()
            assert "pause" in scr.engine.calls
            scr.action_forward()
            assert ("seek", 5) in scr.engine.calls
            scr.action_back()
            assert ("seek", -5) in scr.engine.calls
            # clickable seek + volume bars
            scr.on_click_bar_clicked(ClickBar.Clicked("pl-seek", 0.5))
            assert ("seek_percent", 0.5) in scr.engine.calls
            scr.on_click_bar_clicked(ClickBar.Clicked("pl-vol", 1.0))
            assert any(c[0] == "vol" for c in scr.engine.calls if isinstance(c, tuple))

    run(go())


def test_player_close_returns_to_main():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            scr = await _open_player(app, Video(id="x", title="T", channel="c", duration=100, views=1))
            engine = scr.engine
            await scr.action_close()
            await pilot.pause()
            assert not isinstance(app.screen, PlayerScreen)
            assert "quit" in engine.calls

    run(go())
