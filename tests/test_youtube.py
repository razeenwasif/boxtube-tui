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
    SearchError,
    Video,
    find_ytdlp,
    human_duration,
    human_number,
    search,
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


# ----- network (manual) --------------------------------------------------


@pytest.mark.network
def test_search_live():
    results = search("lofi hip hop", limit=3)
    assert results and all(r.id for r in results)
