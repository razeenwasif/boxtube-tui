"""Tests for boxtube.opener: browser opening, including the WSL path."""

from __future__ import annotations

from boxtube import opener


def test_non_wsl_uses_webbrowser(monkeypatch):
    monkeypatch.setattr(opener, "is_wsl", lambda: False)
    called = {}

    def fake_open(url):
        called["url"] = url
        return True

    monkeypatch.setattr(opener.webbrowser, "open", fake_open)
    assert opener.open_url("https://example.com") is True
    assert called["url"] == "https://example.com"


def test_wsl_prefers_wslview(monkeypatch):
    monkeypatch.setattr(opener, "is_wsl", lambda: True)
    launched = {}

    def fake_which(name):
        return "/usr/bin/wslview" if name == "wslview" else None

    monkeypatch.setattr(opener.shutil, "which", fake_which)
    monkeypatch.setattr(opener.subprocess, "Popen", lambda cmd, **kw: launched.update(cmd=cmd))
    assert opener.open_url("https://youtu.be/x") is True
    assert launched["cmd"][0] == "/usr/bin/wslview"
    assert launched["cmd"][-1] == "https://youtu.be/x"


def test_wsl_falls_back_to_cmd_start(monkeypatch):
    monkeypatch.setattr(opener, "is_wsl", lambda: True)
    monkeypatch.setattr(opener.shutil, "which", lambda name: "/mnt/c/Windows/System32/cmd.exe" if name == "cmd.exe" else None)
    launched = {}
    monkeypatch.setattr(opener.subprocess, "Popen", lambda cmd, **kw: launched.update(cmd=cmd, cwd=kw.get("cwd")))
    assert opener.open_url("https://youtu.be/x") is True
    assert launched["cmd"][:3] == ["/mnt/c/Windows/System32/cmd.exe", "/c", "start"]
    assert launched["cmd"][-1] == "https://youtu.be/x"
    assert launched["cwd"] == "/mnt/c"  # avoids cmd.exe UNC-path warning
