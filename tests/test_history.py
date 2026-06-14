"""Tests for boxtube.history and the search-history suggester."""

from __future__ import annotations

import asyncio

import pytest

from boxtube import history
from boxtube.app import HistorySuggester


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("BOXTUBE_HISTORY", str(tmp_path / "search_history.json"))


# ----- store -------------------------------------------------------------


def test_add_and_recent_most_recent_first():
    history.add("first")
    history.add("second")
    assert history.recent() == ["second", "first"]


def test_dedupe_moves_to_front_case_insensitive():
    history.add("Lofi")
    history.add("jazz")
    history.add("LOFI")
    assert history.recent() == ["LOFI", "jazz"]  # one Lofi, newest casing, at front


def test_blank_query_ignored():
    history.add("   ")
    history.add("")
    assert history.recent() == []


def test_cap_to_max_items(monkeypatch):
    monkeypatch.setattr(history, "MAX_ITEMS", 3)
    for i in range(5):
        history.add(f"q{i}")
    assert history.recent() == ["q4", "q3", "q2"]


def test_clear():
    history.add("x")
    history.clear()
    assert history.recent() == []


def test_corrupt_file_ignored(tmp_path, monkeypatch):
    path = tmp_path / "search_history.json"
    path.write_text("garbage{", encoding="utf-8")
    monkeypatch.setenv("BOXTUBE_HISTORY", str(path))
    assert history.recent() == []
    history.add("ok")
    assert history.recent() == ["ok"]


# ----- suggester ---------------------------------------------------------


def _suggest(value: str):
    # Textual casefolds the value before calling get_suggestion (case-insensitive).
    return asyncio.run(HistorySuggester().get_suggestion(value.casefold()))


def test_suggester_completes_prefix():
    history.add("python tutorial")
    history.add("rust basics")
    assert _suggest("rust") == "rust basics"
    assert _suggest("py") == "python tutorial"


def test_suggester_empty_value_returns_latest():
    history.add("older")
    history.add("newest")
    assert _suggest("") == "newest"


def test_suggester_no_match_returns_none():
    history.add("cooking")
    assert _suggest("zzz") is None
