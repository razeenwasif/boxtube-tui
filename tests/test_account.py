"""Tests for boxtube.account: config paths and sign-in detection."""

from __future__ import annotations

from pathlib import Path

from boxtube import account


def _clear(monkeypatch):
    monkeypatch.delenv("BOXTUBE_COOKIES", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def test_config_dir_respects_xdg(tmp_path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert account.config_dir() == tmp_path / "boxtube"


def test_cookies_path_default(tmp_path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert account.cookies_path() == tmp_path / "boxtube" / "cookies.txt"


def test_cookies_path_override(tmp_path, monkeypatch):
    _clear(monkeypatch)
    target = tmp_path / "custom" / "ck.txt"
    monkeypatch.setenv("BOXTUBE_COOKIES", str(target))
    assert account.cookies_path() == target


def test_signed_out_when_missing(tmp_path, monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BOXTUBE_COOKIES", str(tmp_path / "nope.txt"))
    assert account.is_signed_in() is False
    assert account.cookies_arg() is None


def test_signed_in_when_present(tmp_path, monkeypatch):
    _clear(monkeypatch)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tx\ty\n")
    monkeypatch.setenv("BOXTUBE_COOKIES", str(cookies))
    assert account.is_signed_in() is True
    assert account.cookies_arg() == str(cookies)


def test_empty_cookies_file_is_signed_out(tmp_path, monkeypatch):
    _clear(monkeypatch)
    empty = tmp_path / "cookies.txt"
    empty.write_text("")
    monkeypatch.setenv("BOXTUBE_COOKIES", str(empty))
    assert account.is_signed_in() is False
