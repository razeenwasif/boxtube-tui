"""Tests for boxtube.engine: IPC request/response and control commands.

These use a fake unix-socket stand-in, so no real mpv process is launched.
"""

from __future__ import annotations

import json
import shutil

import pytest

from boxtube.engine import MpvEngine


class FakeSock:
    """A minimal mpv-IPC stand-in: replies to get_property, acks commands."""

    def __init__(self, props: dict, chunk: int = 65536):
        self.props = props
        self.sent: list[dict] = []
        self._out = b""
        self._chunk = chunk

    def sendall(self, data: bytes) -> None:
        msg = json.loads(data.decode())
        self.sent.append(msg)
        rid = msg.get("request_id")
        cmd = msg["command"]
        if cmd[0] == "get_property":
            val = self.props.get(cmd[1])
            reply = {
                "error": "success" if val is not None else "property unavailable",
                "data": val,
                "request_id": rid,
            }
        else:
            reply = {"error": "success", "request_id": rid}
        self._out += (json.dumps(reply) + "\n").encode()

    def recv(self, n: int) -> bytes:
        take = min(self._chunk, n, len(self._out))
        chunk, self._out = self._out[:take], self._out[take:]
        return chunk

    def close(self):
        pass


@pytest.fixture
def engine():
    e = MpvEngine("https://youtu.be/x")
    yield e
    shutil.rmtree(e._dir, ignore_errors=True)


def test_get_property_success(engine):
    engine._sock = FakeSock({"duration": 213.0, "pause": False})
    assert engine.get("duration") == 213.0
    assert engine.get("pause") is False


def test_get_property_unavailable_returns_none(engine):
    engine._sock = FakeSock({})
    assert engine.get("time-pos") is None


def test_get_property_handles_chunked_socket(engine):
    # recv hands back one byte at a time — exercises the line buffer.
    engine._sock = FakeSock({"volume": 100.0}, chunk=1)
    assert engine.get("volume") == 100.0


def test_command_serialization(engine):
    sock = FakeSock({})
    engine._sock = sock
    engine.toggle_pause()
    engine.seek(-5)
    engine.seek_percent(0.5)
    engine.set_volume(80)
    cmds = [m["command"] for m in sock.sent]
    assert ["cycle", "pause"] in cmds
    assert ["seek", -5, "relative"] in cmds
    assert ["seek", 50.0, "absolute-percent"] in cmds
    assert ["set_property", "volume", 80] in cmds


def test_volume_and_seek_clamping(engine):
    sock = FakeSock({})
    engine._sock = sock
    engine.set_volume(999)
    engine.set_volume(-50)
    engine.seek_percent(2.0)
    engine.seek_percent(-1.0)
    cmds = [m["command"] for m in sock.sent]
    assert ["set_property", "volume", 130.0] in cmds
    assert ["set_property", "volume", 0.0] in cmds
    assert ["seek", 100.0, "absolute-percent"] in cmds
    assert ["seek", 0.0, "absolute-percent"] in cmds


def test_build_command_shape(engine):
    cmd = engine._build_command()
    assert cmd[-1] == "https://youtu.be/x"
    assert "--vo=null" in cmd
    assert any(c.startswith("--input-ipc-server=") for c in cmd)
    assert any(c.startswith("--ytdl-format=") for c in cmd)
    assert any("player_client=" in c and "android_vr" in c for c in cmd)
