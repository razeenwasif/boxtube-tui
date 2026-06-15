"""Tests for the comments modal screen (fake fetch, no network)."""

from __future__ import annotations

import asyncio

import pytest

from boxtube.app import BoxTube
from boxtube.comments_screen import CommentRow, CommentsScreen
from boxtube.youtube import Comment, SearchError, Video


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path, fake_image):
    monkeypatch.setenv("BOXTUBE_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr("boxtube.thumbnails.fetch", lambda vid, url: fake_image)
    monkeypatch.setattr("boxtube.account.is_signed_in", lambda: False)
    monkeypatch.setattr("boxtube.account.cookies_arg", lambda: None)
    # Safety net: never hit the network from the worker unless a test overrides it.
    monkeypatch.setattr("boxtube.youtube.fetch_comments", lambda *a, **k: [])


_VIDEO = Video(id="vid", title="A Video", channel="Chan", duration=100, views=10)


async def _open_and_wait(app, video=_VIDEO):
    app.push_screen(CommentsScreen(video))
    for _ in range(100):
        await asyncio.sleep(0.03)
        scr = app.screen
        if isinstance(scr, CommentsScreen):
            rows = list(scr.query(CommentRow))
            empties = list(scr.query(".comment-empty"))
            if rows or empties:
                return scr, rows, empties
    raise AssertionError("comments screen never finished loading")


def test_renders_comment_rows(monkeypatch):
    monkeypatch.setattr(
        "boxtube.youtube.fetch_comments",
        lambda *a, **k: [
            Comment(author="@a", text="first", likes=5, time_text="1 day ago"),
            Comment(author="@maker", text="thanks", is_uploader=True),
        ],
    )

    async def go():
        app = BoxTube()
        async with app.run_test():
            scr, rows, empties = await _open_and_wait(app)
            assert len(rows) == 2 and not empties
            scr.action_close()

    run(go())


def test_empty_state_when_no_comments(monkeypatch):
    monkeypatch.setattr("boxtube.youtube.fetch_comments", lambda *a, **k: [])

    async def go():
        app = BoxTube()
        async with app.run_test():
            scr, rows, empties = await _open_and_wait(app)
            assert not rows and len(empties) == 1
            scr.action_close()

    run(go())


def test_error_state_when_fetch_fails(monkeypatch):
    def _boom(*a, **k):
        raise SearchError("yt-dlp blew up")

    monkeypatch.setattr("boxtube.youtube.fetch_comments", _boom)

    async def go():
        app = BoxTube()
        async with app.run_test():
            scr, rows, empties = await _open_and_wait(app)
            assert not rows and len(empties) == 1  # error shown in the empty slot
            scr.action_close()

    run(go())


def test_action_comments_opens_screen():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._focused_item = _VIDEO
            app.action_comments()
            await pilot.pause()
            assert isinstance(app.screen, CommentsScreen)
            app.screen.action_close()

    run(go())


def test_action_comments_without_video_is_noop():
    async def go():
        app = BoxTube()
        async with app.run_test() as pilot:
            app._focused_item = None
            app.action_comments()
            await pilot.pause()
            assert not isinstance(app.screen, CommentsScreen)

    run(go())
