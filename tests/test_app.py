"""Headless UI tests for boxtube.app using Textual's run_test harness.

These avoid the network: thumbnail fetching is monkeypatched, and we populate the
results list directly instead of calling the live search.
"""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Input, ListView, Static
from textual_image.widget import Image

from boxtube import player as player_mod
from boxtube import thumbnails as thumb_mod
from boxtube.app import BoxTube
from boxtube.youtube import Video


def run(coro):
    """Run an async coroutine in a fresh event loop (no pytest-asyncio needed)."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _offline_thumbnails(monkeypatch, fake_image):
    """Make every thumbnail fetch return a local image — never hit the network."""
    monkeypatch.setattr(thumb_mod, "fetch", lambda video_id, url: fake_image)


def test_boot_has_all_widgets():
    async def go():
        app = BoxTube()
        async with app.run_test(size=(120, 34)):
            for sel in (
                "#appbar", "#brand", "#brand-hint", "#search",
                "#results", "#detail-pane", "#thumb", "#meta", "#desc",
            ):
                app.query_one(sel)  # raises if missing
            assert app.query_one("#search", Input).has_focus

    run(go())


def test_populate_highlights_first(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate(sample_videos)
            await pilot.pause()
            assert app._current_video_id == sample_videos[0].id
            title = app.query_one("#results", ListView).border_title
            assert title == f"Results ({len(sample_videos)})"

    run(go())


def test_navigation_updates_current(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate(sample_videos)
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert app._current_video_id == sample_videos[1].id

    run(go())


def test_details_render_escapes_markup():
    """A title/description containing brackets must not break console markup."""
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            v = Video(
                id="z9",
                title="Weird [b]title[/b]",
                channel="Chan [x]",
                duration=61,
                views=1234,
                description="[Music] intro then text",
            )
            app._show_details(v)
            await pilot.pause()
            assert app._current_video_id == "z9"
            # Rendering succeeded (no MarkupError raised during update).
            assert isinstance(app.query_one("#meta", Static), Static)

    run(go())


def test_thumbnail_stale_guard(sample_videos, fake_image):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate(sample_videos)
            await pilot.pause()
            app._current_video_id = sample_videos[0].id

            # Applying for a non-current id is a no-op (and must not raise).
            app._apply_thumbnail("not-current", fake_image)
            await pilot.pause()

            # Applying for the current id updates the widget.
            app._apply_thumbnail(sample_videos[0].id, fake_image)
            await pilot.pause()
            assert app.query_one("#thumb", Image).image.size == (320, 180)

    run(go())


def test_play_without_selection_warns(monkeypatch):
    async def go():
        app = BoxTube()
        async with app.run_test():
            notes: list = []
            monkeypatch.setattr(app, "notify", lambda *a, **k: notes.append((a, k)))
            app.action_play()  # nothing highlighted
            assert notes, "expected a warning notification"

    run(go())


def test_play_without_mpv_notifies(sample_videos, monkeypatch):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate(sample_videos)
            await pilot.pause()
            monkeypatch.setattr(player_mod, "mpv_path", lambda: None)
            notes: list = []
            monkeypatch.setattr(app, "notify", lambda *a, **k: notes.append((a, k)))
            app.action_play()
            await pilot.pause()
            assert any("mpv" in str(a).lower() for a, _ in notes)

    run(go())
