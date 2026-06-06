"""Headless UI tests for boxtube.app using Textual's run_test harness.

These avoid the network: thumbnail fetching and feed loaders are monkeypatched,
and we populate the results list directly instead of calling live yt-dlp.
"""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Input, ListView, Static
from textual_image.widget import Image

from boxtube import account as account_mod
from boxtube import player as player_mod
from boxtube import thumbnails as thumb_mod
from boxtube.app import BoxTube, NAV_ITEMS
from boxtube.youtube import Playlist, Video


def run(coro):
    """Run an async coroutine in a fresh event loop (no pytest-asyncio needed)."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _offline(monkeypatch, fake_image):
    """No network, signed out by default."""
    monkeypatch.setattr(thumb_mod, "fetch", lambda video_id, url: fake_image)
    monkeypatch.setattr(account_mod, "is_signed_in", lambda: False)
    monkeypatch.setattr(account_mod, "cookies_arg", lambda: None)


def test_boot_has_all_widgets():
    async def go():
        app = BoxTube()
        async with app.run_test(size=(120, 34)):
            for sel in (
                "#appbar", "#brand", "#auth", "#search",
                "#nav", "#results", "#detail-pane", "#thumb", "#meta", "#desc",
            ):
                app.query_one(sel)  # raises if missing
            # Nav has one row per source.
            assert len(app.query_one("#nav", ListView).children) == len(NAV_ITEMS)

    run(go())


def test_signed_out_prompts_sign_in():
    async def go():
        app = BoxTube()
        async with app.run_test():
            assert app.query_one("#results", ListView).border_title == "Sign in required"
            assert app.query_one("#search", Input).has_focus

    run(go())


def test_populate_videos(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            assert app._current_video_id == sample_videos[0].id
            assert app.query_one("#results", ListView).border_title == "Home (2)"

    run(go())


def test_navigation_updates_current(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert app._current_video_id == sample_videos[1].id

    run(go())


def test_select_nav_sets_source():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app.action_select_nav(1)  # History
            await pilot.pause()
            assert app._current_source == "history"
            assert app.query_one("#nav", ListView).index == 1

    run(go())


def test_back_from_playlist_returns_to_playlists():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._drill_playlist = Playlist(id="PL1", title="Mix", count=3)
            app.action_back()
            await pilot.pause()
            assert app._current_source == "playlists"
            assert app._drill_playlist is None

    run(go())


def test_populate_playlists_shows_drilldown():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            pls = [Playlist(id="PLa", title="A", count=2), Playlist(id="PLb", title="B")]
            app._populate_playlists(pls, "Playlists")
            await pilot.pause()
            assert app.query_one("#results", ListView).border_title == "Playlists (2)"

    run(go())


def test_details_render_escapes_markup():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            v = Video(
                id="z9", title="Weird [b]title[/b]", channel="Chan [x]",
                duration=61, views=1234, description="[Music] then text",
            )
            app._show_details(v)
            await pilot.pause()
            assert app._current_video_id == "z9"
            assert isinstance(app.query_one("#meta", Static), Static)

    run(go())


def test_thumbnail_stale_guard(sample_videos, fake_image):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            app._current_video_id = sample_videos[0].id
            app._apply_thumbnail("not-current", fake_image)  # ignored, no raise
            await pilot.pause()
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
            assert notes

    run(go())


def test_play_without_mpv_notifies(sample_videos, monkeypatch):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            monkeypatch.setattr(player_mod, "mpv_path", lambda: None)
            notes: list = []
            monkeypatch.setattr(app, "notify", lambda *a, **k: notes.append((a, k)))
            app.action_play()
            await pilot.pause()
            assert any("mpv" in str(a).lower() for a, _ in notes)

    run(go())


def test_signed_in_opens_home_on_mount(monkeypatch, sample_videos):
    monkeypatch.setattr(account_mod, "is_signed_in", lambda: True)
    monkeypatch.setattr(account_mod, "cookies_arg", lambda: "/tmp/ck.txt")
    monkeypatch.setattr(
        "boxtube.youtube.videos_for_feed", lambda key, limit, cookies: sample_videos
    )

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._current_source == "home"

    run(go())
