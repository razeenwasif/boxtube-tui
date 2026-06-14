"""Tests for boxtube.progress: the per-video resume store."""

from __future__ import annotations

import pytest

from boxtube import progress


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("BOXTUBE_PROGRESS", str(tmp_path / "watch_progress.json"))


def test_record_and_resume_round_trip():
    progress.record("vid1", 90.0, 600.0, "A video")
    assert progress.resume_at("vid1") == 90.0
    assert progress.load()["vid1"]["title"] == "A video"


def test_unknown_video_has_no_resume():
    assert progress.resume_at("nope") is None


def test_tiny_position_is_not_stored():
    progress.record("vid", 3.0, 600.0)
    assert progress.resume_at("vid") is None
    assert "vid" not in progress.load()


def test_finished_video_is_cleared():
    progress.record("vid", 100.0, 600.0)   # mid-watch → stored
    assert progress.resume_at("vid") == 100.0
    progress.record("vid", 595.0, 600.0)   # watched to (near) the end → forgotten
    assert progress.resume_at("vid") is None
    assert "vid" not in progress.load()


def test_clear_forgets_entry():
    progress.record("vid", 90.0, 600.0)
    progress.clear("vid")
    assert progress.resume_at("vid") is None


def test_prune_keeps_most_recent(monkeypatch):
    monkeypatch.setattr(progress, "MAX_ENTRIES", 3)
    for i in range(6):
        progress.record(f"v{i}", 60.0 + i, 600.0)
    items = progress.load()
    assert len(items) == 3
    assert set(items) == {"v3", "v4", "v5"}  # the three most recent writes


def test_corrupt_file_is_ignored(tmp_path, monkeypatch):
    path = tmp_path / "watch_progress.json"
    path.write_text("not json{", encoding="utf-8")
    monkeypatch.setenv("BOXTUBE_PROGRESS", str(path))
    assert progress.load() == {}            # unreadable → empty, no crash
    progress.record("vid", 90.0, 600.0)     # recovers by overwriting
    assert progress.resume_at("vid") == 90.0
