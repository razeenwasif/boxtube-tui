"""Tests for boxtube.player: video-output detection and command building."""

from __future__ import annotations

import pytest

from boxtube import player


# ----- detect_vo ---------------------------------------------------------


def _clear_term_env(monkeypatch):
    for var in ("BOXTUBE_VO", "TERM", "TERM_PROGRAM", "KITTY_WINDOW_ID", "WEZTERM_PANE"):
        monkeypatch.delenv(var, raising=False)


def test_detect_vo_explicit_override(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("BOXTUBE_VO", "sixel")
    monkeypatch.setenv("TERM", "xterm-kitty")  # override wins regardless
    assert player.detect_vo() == "sixel"


def test_detect_vo_kitty_by_window_id(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("KITTY_WINDOW_ID", "1")
    assert player.detect_vo() == "kitty"


def test_detect_vo_ghostty(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("TERM_PROGRAM", "ghostty")
    assert player.detect_vo() == "kitty"


def test_detect_vo_wezterm(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("WEZTERM_PANE", "0")
    assert player.detect_vo() == "kitty"


def test_detect_vo_sixel(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("TERM", "foot")
    assert player.detect_vo() == "sixel"


def test_detect_vo_default_tct(monkeypatch):
    _clear_term_env(monkeypatch)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert player.detect_vo() == "tct"


# ----- detect_hwdec ------------------------------------------------------


def test_detect_hwdec_default(monkeypatch):
    monkeypatch.delenv("BOXTUBE_HWDEC", raising=False)
    assert player.detect_hwdec() == "auto-safe"


def test_detect_hwdec_override(monkeypatch):
    monkeypatch.setenv("BOXTUBE_HWDEC", "vaapi")
    assert player.detect_hwdec() == "vaapi"


def test_detect_hwdec_disabled(monkeypatch):
    monkeypatch.setenv("BOXTUBE_HWDEC", "")
    assert player.detect_hwdec() is None


# ----- build_command -----------------------------------------------------


def test_build_command_core(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: "/opt/yt-dlp")
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("https://youtu.be/X", vo="kitty")

    assert cmd[0] == "/usr/bin/mpv"
    assert "--vo=kitty" in cmd
    assert cmd[-1] == "https://youtu.be/X"
    assert any(c.startswith("--ytdl-format=") for c in cmd)
    assert "--script-opts=ytdl_hook-ytdl_path=/opt/yt-dlp" in cmd
    assert "--hwdec=auto-safe" in cmd
    # JS-free clients forced so extraction works without a JS runtime
    assert any("player_client=" in c and "android_vr" in c for c in cmd)
    # sw-fast profile is only for the text output
    assert "--profile=sw-fast" not in cmd


def test_build_command_keeps_errors_visible(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: "/opt/yt-dlp")
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="kitty")
    # --really-quiet would suppress playback errors too; must not be present.
    assert "--really-quiet" not in cmd
    assert "--msg-level=all=error" in cmd


def test_build_command_includes_js_runtime(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: "/opt/yt-dlp")
    monkeypatch.setattr(player, "find_js_runtime", lambda: "deno")
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="kitty")
    assert "--ytdl-raw-options-append=js-runtimes=deno" in cmd


def test_build_command_no_js_runtime(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: "/opt/yt-dlp")
    monkeypatch.setattr(player, "find_js_runtime", lambda: None)
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="kitty")
    assert not any("js-runtimes" in c for c in cmd)


def test_build_command_includes_cookies(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: "/opt/yt-dlp")
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="kitty", cookies="/ck.txt")
    assert any(c == "--ytdl-raw-options-append=cookies=/ck.txt" for c in cmd)
    # no cookies -> no cookies option
    cmd2 = player.build_command("url", vo="kitty")
    assert not any("cookies=" in c for c in cmd2)


def test_build_command_tct_adds_swfast(monkeypatch):
    monkeypatch.setattr(player, "find_ytdlp", lambda: None)
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="tct")
    assert "--profile=sw-fast" in cmd
    # no yt-dlp found -> no script-opts entry
    assert not any("ytdl_path" in c for c in cmd)


def test_build_command_omits_disabled_hwdec(monkeypatch):
    monkeypatch.setenv("BOXTUBE_HWDEC", "")
    monkeypatch.setattr(player, "find_ytdlp", lambda: None)
    monkeypatch.setattr(player, "mpv_path", lambda: "/usr/bin/mpv")
    cmd = player.build_command("url", vo="kitty")
    assert not any(c.startswith("--hwdec=") for c in cmd)


def test_play_raises_without_mpv(monkeypatch):
    monkeypatch.setattr(player, "mpv_path", lambda: None)
    with pytest.raises(FileNotFoundError):
        player.play("url")
