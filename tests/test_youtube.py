"""Tests for boxtube.youtube: formatting, model, discovery, and parsing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from boxtube import youtube
from boxtube.youtube import (
    Playlist,
    SearchError,
    Video,
    find_ytdlp,
    human_duration,
    human_number,
    search,
    user_playlists,
    videos_for_feed,
)


# ----- formatting helpers ------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "—"),
        (0, "0"),
        (999, "999"),
        (1000, "1.0K"),
        (55_200_000, "55.2M"),
        (1_600_000_000, "1.6B"),
    ],
)
def test_human_number(value, expected):
    assert human_number(value) == expected


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (None, "—"),
        (0, "—"),
        (5, "0:05"),
        (65, "1:05"),
        (3661, "1:01:01"),
        (22258, "6:10:58"),
    ],
)
def test_human_duration(seconds, expected):
    assert human_duration(seconds) == expected


# ----- Video model -------------------------------------------------------


def test_video_properties():
    v = Video(id="xyz", title="t", channel="c", duration=125, views=1500)
    assert v.watch_url == "https://www.youtube.com/watch?v=xyz"
    assert v.thumbnail_url == "https://i.ytimg.com/vi/xyz/mqdefault.jpg"
    assert v.duration_str == "2:05"
    assert v.views_str == "1.5K"


# ----- find_ytdlp --------------------------------------------------------


def test_find_ytdlp_prefers_interpreter_sibling(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "yt-dlp"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)

    monkeypatch.setattr(sys, "executable", str(bindir / "python"))
    # Even if PATH has another one, the sibling wins.
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/bin/yt-dlp")

    assert find_ytdlp() == str(fake)


def test_find_ytdlp_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(youtube.shutil, "which", lambda _: "/usr/bin/yt-dlp")
    assert find_ytdlp() == "/usr/bin/yt-dlp"


def test_find_ytdlp_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(youtube.shutil, "which", lambda _: None)
    assert find_ytdlp() is None


# ----- search parsing (mocked subprocess) --------------------------------


def _fake_run_factory(stdout: str, stderr: str = "", returncode: int = 0):
    def _fake_run(cmd, capture_output=True, text=True):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    return _fake_run


def test_search_parses_entries(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    lines = "\n".join(
        json.dumps(d)
        for d in [
            {"id": "a1", "title": "First", "channel": "Chan", "duration": 100, "view_count": 2000},
            {"id": "b2", "title": "Second", "uploader": "Up", "duration": None, "view_count": None},
            {"_type": "playlist", "id": "skip"},  # should be skipped
            {"title": "no id"},  # should be skipped
        ]
    )
    monkeypatch.setattr(youtube.subprocess, "run", _fake_run_factory(lines))

    results = search("anything")
    assert [v.id for v in results] == ["a1", "b2"]
    assert results[0].channel == "Chan"
    assert results[1].channel == "Up"          # falls back to uploader
    assert results[1].duration_str == "—"


def test_search_skips_malformed_json(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    stdout = '{"id": "ok", "title": "Good"}\nNOT JSON\n'
    monkeypatch.setattr(youtube.subprocess, "run", _fake_run_factory(stdout))
    results = search("q")
    assert len(results) == 1 and results[0].id == "ok"


def test_search_empty_query_returns_empty(monkeypatch):
    # Must not even attempt to run yt-dlp.
    monkeypatch.setattr(
        youtube, "find_ytdlp", lambda: (_ for _ in ()).throw(AssertionError("called"))
    )
    assert search("   ") == []


def test_search_raises_on_no_output(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    monkeypatch.setattr(
        youtube.subprocess, "run", _fake_run_factory("", stderr="boom", returncode=1)
    )
    with pytest.raises(SearchError):
        search("q")


def test_search_builds_expected_command(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    captured = {}

    def _capture(cmd, capture_output=True, text=True):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout='{"id":"x","title":"t"}', stderr="", returncode=0)

    monkeypatch.setattr(youtube.subprocess, "run", _capture)
    search("cats", limit=7)
    assert captured["cmd"][1] == "ytsearch7:cats"
    assert "--flat-playlist" in captured["cmd"]
    assert "--dump-json" in captured["cmd"]


# ----- find_js_runtime ---------------------------------------------------


def test_find_js_runtime_prefers_native(monkeypatch):
    monkeypatch.delenv("BOXTUBE_JS_RUNTIME", raising=False)
    table = {"deno": None, "bun": "/home/u/.bun/bin/bun", "node": "/usr/bin/node"}
    monkeypatch.setattr(youtube.shutil, "which", lambda name: table.get(name))
    assert youtube.find_js_runtime() == "bun"


def test_find_js_runtime_skips_windows_exe(monkeypatch):
    monkeypatch.delenv("BOXTUBE_JS_RUNTIME", raising=False)
    monkeypatch.setattr(
        youtube.shutil, "which",
        lambda name: "/mnt/c/Program Files/nodejs/node.exe" if name == "node" else None,
    )
    assert youtube.find_js_runtime() is None


def test_find_js_runtime_override(monkeypatch):
    monkeypatch.setenv("BOXTUBE_JS_RUNTIME", "deno:/opt/deno")
    assert youtube.find_js_runtime() == "deno:/opt/deno"


def test_find_js_runtime_disabled(monkeypatch):
    monkeypatch.setenv("BOXTUBE_JS_RUNTIME", "")
    assert youtube.find_js_runtime() is None


# ----- Playlist model ----------------------------------------------------


def test_playlist_model():
    p = Playlist(id="PL123", title="My mix", count=12)
    assert p.url == "https://www.youtube.com/playlist?list=PL123"
    assert p.count_str == "12 videos"
    assert Playlist(id="PL", title="t").count_str == "playlist"


# ----- feeds & dispatch (mocked subprocess) ------------------------------


def test_entries_passes_cookies_and_limit(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    captured = {}

    def _capture(cmd, capture_output=True, text=True):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout='{"id":"vvvvvvvvvvv","title":"t"}', stderr="", returncode=0)

    monkeypatch.setattr(youtube.subprocess, "run", _capture)
    youtube.liked_videos(limit=9, cookies="/path/ck.txt")
    cmd = captured["cmd"]
    assert "--cookies" in cmd and "/path/ck.txt" in cmd
    assert "--playlist-end" in cmd and "9" in cmd
    assert youtube.PLAYLIST_LIKED in cmd


def test_videos_for_feed_dispatch(monkeypatch):
    sentinel = [Video(id="x", title="t", channel="c", duration=1, views=1)]
    monkeypatch.setattr(youtube, "subscriptions_feed", lambda limit, cookies: sentinel)
    monkeypatch.setattr(youtube, "watch_history", lambda limit, cookies: sentinel)
    monkeypatch.setattr(youtube, "liked_videos", lambda limit, cookies: sentinel)
    monkeypatch.setattr(youtube, "watch_later", lambda limit, cookies: sentinel)

    for key in ("home", "subscriptions", "history", "liked", "watch_later"):
        assert videos_for_feed(key, limit=5, cookies=None) is sentinel

    with pytest.raises(ValueError):
        videos_for_feed("bogus", limit=5, cookies=None)


def test_subscribed_channels_parsing(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    lines = "\n".join(
        json.dumps(d)
        for d in [
            {"id": "UCabc123", "ie_key": "YoutubeTab", "title": "Cool Channel",
             "url": "https://www.youtube.com/channel/UCabc123"},
            {"title": "no id, skipped"},
            {"id": "PLnope", "ie_key": "YoutubeTab", "title": "a playlist not a channel"},
        ]
    )
    monkeypatch.setattr(youtube.subprocess, "run", _fake_run_factory(lines))
    channels = youtube.subscribed_channels(cookies="/ck")
    assert [c.id for c in channels] == ["UCabc123"]
    assert channels[0].name == "Cool Channel"
    assert channels[0].videos_url == "https://www.youtube.com/channel/UCabc123/videos"


def test_user_playlists_parsing(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    lines = "\n".join(
        json.dumps(d)
        for d in [
            {"id": "PLaaa", "ie_key": "YoutubeTab", "title": "Mix A",
             "url": "https://www.youtube.com/playlist?list=PLaaa", "playlist_count": 4},
            {"id": "vvvvvvvvvvv", "ie_key": "Youtube", "title": "a video"},  # not a playlist
        ]
    )
    monkeypatch.setattr(youtube.subprocess, "run", _fake_run_factory(lines))
    playlists = user_playlists(cookies="/ck")
    assert [p.id for p in playlists] == ["PLaaa"]
    assert playlists[0].count == 4


def test_feed_separates_videos_from_playlists(monkeypatch):
    monkeypatch.setattr(youtube, "find_ytdlp", lambda: "/usr/bin/yt-dlp")
    lines = "\n".join(
        json.dumps(d)
        for d in [
            {"id": "vvvvvvvvvvv", "ie_key": "Youtube", "title": "Real video", "view_count": 10},
            {"id": "PLxxx", "ie_key": "YoutubeTab", "title": "A playlist row"},
        ]
    )
    monkeypatch.setattr(youtube.subprocess, "run", _fake_run_factory(lines))
    videos = youtube.subscriptions_feed(cookies="/ck")
    assert [v.id for v in videos] == ["vvvvvvvvvvv"]


# ----- network (manual) --------------------------------------------------


@pytest.mark.network
def test_search_live():
    results = search("lofi hip hop", limit=3)
    assert results and all(r.id for r in results)
