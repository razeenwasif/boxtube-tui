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
    # Stub the yt-dlp-backed loaders so no test ever spawns a real subprocess
    # (even when a test forces "signed in" and on_mount loads feeds/channels).
    monkeypatch.setattr("boxtube.youtube.subscribed_channels", lambda **k: [])
    monkeypatch.setattr("boxtube.youtube.videos_for_feed", lambda *a, **k: [])
    monkeypatch.setattr("boxtube.youtube.user_playlists", lambda **k: [])
    monkeypatch.setattr("boxtube.youtube.search", lambda *a, **k: [])


def test_boot_has_all_widgets():
    async def go():
        app = BoxTube()
        async with app.run_test(size=(120, 34)):
            for sel in (
                "#appbar", "#brand", "#search", "#auth", "#chips",
                "#sidebar", "#nav", "#subs", "#grid", "#grid-inner", "#detail-pane",
                "#thumb", "#meta", "#desc",
            ):
                app.query_one(sel)  # raises if missing
            # Nav has one row per source.
            assert len(app.query_one("#nav", ListView).children) == len(NAV_ITEMS)

    run(go())


def test_chip_search_runs_query(monkeypatch):
    from boxtube.app import Chip

    captured = {}
    monkeypatch.setattr(BoxTube, "run_search", lambda self, q: captured.setdefault("q", q))

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app.on_chip_selected(Chip.Selected("Music"))
            await pilot.pause()
            assert captured.get("q") == "Music"
            # the chip becomes the active one
            active = [c.label for c in app.query(Chip) if c.has_class("-active")]
            assert active == ["Music"]

    run(go())


def test_chip_shorts_loads_shorts(monkeypatch):
    from boxtube.app import Chip

    called = {}
    monkeypatch.setattr(BoxTube, "run_shorts", lambda self: called.setdefault("hit", True))

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app.on_chip_selected(Chip.Selected("Shorts"))
            await pilot.pause()
            assert called.get("hit") is True
            assert app._shorts_active is True
            active = [c.label for c in app.query(Chip) if c.has_class("-active")]
            assert active == ["Shorts"]

    run(go())


def test_chip_all_opens_home(monkeypatch):
    from boxtube.app import Chip

    opened = {}
    monkeypatch.setattr(BoxTube, "_open_source", lambda self, key: opened.setdefault("key", key))

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app.on_chip_selected(Chip.Selected("All"))
            await pilot.pause()
            assert opened.get("key") == "home"

    run(go())


def test_channel_drilldown_and_back():
    from boxtube.app import ChannelItem
    from boxtube.youtube import Channel

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            ch = Channel(id="UCabc", name="Some Channel")
            app.query_one("#subs", ListView).append(ChannelItem(ch))
            await pilot.pause()
            app._open_channel(ch)
            assert app._drill_channel is ch
            app._current_source = "home"
            app.action_back()
            assert app._drill_channel is None and app._current_source == "home"

    run(go())


def test_signed_out_prompts_sign_in():
    async def go():
        app = BoxTube()
        async with app.run_test():
            assert app.query_one("#grid").border_title == "Sign in required"
            assert app.query_one("#search", Input).has_focus

    run(go())


def test_populate_videos(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            await pilot.pause()  # call_after_refresh focuses the first card
            assert len(app._cards) == 2
            assert app.query_one("#grid").border_title == "Home (2)"
            assert app._current_video_id == sample_videos[0].id

    run(go())


def test_navigation_updates_current(sample_videos):
    async def go():
        app = BoxTube()
        async with app.run_test(size=(120, 34)) as pilot:
            app._populate_videos(sample_videos, "Home")
            await pilot.pause()
            await pilot.pause()
            app._cards[1].focus()  # focusing a card updates the preview selection
            await pilot.pause()
            assert app._focused_item is sample_videos[1]
            assert app._current_video_id == sample_videos[1].id

    run(go())


def test_grid_lazy_loads_only_visible_cards():
    async def go():
        app = BoxTube()
        async with app.run_test(size=(120, 30)) as pilot:
            vids = [Video(id=str(i), title=f"T{i}", channel="c", duration=1, views=1) for i in range(40)]
            app._populate_videos(vids, "Home")
            await pilot.pause()
            await pilot.pause()
            # Reset the loaded set so this measures pure region visibility (the
            # worker may already have loaded the on-screen cards by now).
            app._thumbs_loaded = set()
            visible = app._visible_unloaded_cards()
            # Only on-screen cards (+ a small buffer) — not all 40.
            assert 0 < len(visible) < len(vids)

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
            assert app.query_one("#grid").border_title == "Playlists (2)"

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
            await pilot.pause()  # first card focuses -> becomes the selection
            monkeypatch.setattr(player_mod, "mpv_path", lambda: None)
            notes: list = []
            monkeypatch.setattr(app, "notify", lambda *a, **k: notes.append((a, k)))
            app.action_play()
            await pilot.pause()
            assert any("mpv" in str(a).lower() for a, _ in notes)

    run(go())


def test_cookie_trouble_renders():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._show_cookie_trouble("WL: YouTube said: The playlist does not exist.")
            await pilot.pause()
            assert isinstance(app.query_one("#meta", Static), Static)

    run(go())


def test_empty_feed_signed_in_shows_cookie_trouble(monkeypatch):
    monkeypatch.setattr(account_mod, "is_signed_in", lambda: True)
    monkeypatch.setattr(account_mod, "cookies_arg", lambda: "/ck")

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            calls: list = []
            monkeypatch.setattr(app, "_show_cookie_trouble", lambda detail="": calls.append(detail))
            app._current_source = "home"
            app._populate_videos([], "Home")
            await pilot.pause()
            assert calls, "expected cookie-trouble guidance for an empty feed while signed in"

    run(go())


def test_auth_error_shows_cookie_trouble(monkeypatch):
    monkeypatch.setattr(account_mod, "is_signed_in", lambda: True)
    monkeypatch.setattr(account_mod, "cookies_arg", lambda: "/ck")

    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            await pilot.pause()  # let on_mount's startup load settle first
            calls: list = []
            monkeypatch.setattr(app, "_show_cookie_trouble", lambda detail="": calls.append(detail))
            monkeypatch.setattr(app, "notify", lambda *a, **k: None)
            app._on_load_error("LL: YouTube said: The playlist does not exist.")
            assert calls
            assert app.query_one("#grid").border_title == "Sign-in problem"

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
