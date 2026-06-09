"""Tests for boxtube.config: load/save round-trip, coercion, env application."""

from __future__ import annotations

import os

import pytest

from boxtube import config


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("BOXTUBE_CONFIG", str(tmp_path / "config.toml"))
    for setting in config.SCHEMA:
        if setting.env:
            monkeypatch.delenv(setting.env, raising=False)


def test_load_returns_defaults_when_missing():
    assert config.load() == config.defaults()


def test_save_then_load_round_trip():
    values = config.defaults()
    values.update(player_height=720, image_backend="sixel", playback_cookies=True,
                  grid_density="compact", thumb_cache=0)
    config.save(values)
    loaded = config.load()
    assert loaded["player_height"] == 720
    assert loaded["image_backend"] == "sixel"
    assert loaded["playback_cookies"] is True
    assert loaded["grid_density"] == "compact"
    assert loaded["thumb_cache"] == 0


def test_save_coerces_out_of_range_and_bad_choice():
    values = config.defaults()
    values.update(player_height=99999, image_backend="bogus", player_fps="notanint")
    config.save(values)
    loaded = config.load()
    assert loaded["player_height"] == 1080          # clamped to max
    assert loaded["image_backend"] == "auto"        # bad choice → default
    assert loaded["player_fps"] == config.defaults()["player_fps"]  # bad int → default


def test_apply_to_env_setdefault_respects_shell(monkeypatch):
    monkeypatch.setenv("BOXTUBE_PLAYER_HEIGHT", "240")  # shell wins
    values = config.defaults()
    values["player_height"] = 720
    values["player_fps"] = 30
    config.apply_to_env(values, overwrite=False)
    assert os.environ["BOXTUBE_PLAYER_HEIGHT"] == "240"   # not overridden
    assert os.environ["BOXTUBE_PLAYER_FPS"] == "30"       # filled from config


def test_apply_to_env_overwrite_and_auto_blank():
    values = config.defaults()
    values["image_backend"] = "auto"
    values["playback_cookies"] = False
    config.apply_to_env(values, overwrite=True)
    assert os.environ["BOXTUBE_IMAGE_BACKEND"] == ""     # auto → empty
    assert os.environ["BOXTUBE_PLAYBACK_COOKIES"] == ""  # off → empty (falsy)
