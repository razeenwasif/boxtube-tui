"""Tests for thumbnail fetching and cache bounds."""

from __future__ import annotations

from io import BytesIO

from PIL import Image as PILImage

from boxtube import thumbnails


class _Response:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self) -> bytes:
        return self._data


def _image_bytes() -> bytes:
    buf = BytesIO()
    PILImage.new("RGB", (8, 8), (200, 20, 20)).save(buf, format="JPEG")
    return buf.getvalue()


def test_fetch_uses_lru_cache(monkeypatch):
    thumbnails.clear_cache()
    monkeypatch.setenv("BOXTUBE_THUMB_CACHE_SIZE", "2")
    calls: list[str] = []
    data = _image_bytes()

    def fake_urlopen(req, timeout=10):
        calls.append(req.full_url)
        return _Response(data)

    monkeypatch.setattr(thumbnails.urllib.request, "urlopen", fake_urlopen)

    first = thumbnails.fetch("a", "https://example.test/a.jpg")
    thumbnails.fetch("b", "https://example.test/b.jpg")
    assert thumbnails.fetch("a", "https://example.test/a.jpg") is first

    thumbnails.fetch("c", "https://example.test/c.jpg")
    thumbnails.fetch("b", "https://example.test/b.jpg")

    assert calls == [
        "https://example.test/a.jpg",
        "https://example.test/b.jpg",
        "https://example.test/c.jpg",
        "https://example.test/b.jpg",
    ]
    thumbnails.clear_cache()


def test_cache_can_be_disabled(monkeypatch):
    thumbnails.clear_cache()
    monkeypatch.setenv("BOXTUBE_THUMB_CACHE_SIZE", "0")
    calls: list[str] = []
    data = _image_bytes()

    def fake_urlopen(req, timeout=10):
        calls.append(req.full_url)
        return _Response(data)

    monkeypatch.setattr(thumbnails.urllib.request, "urlopen", fake_urlopen)

    thumbnails.fetch("a", "https://example.test/a.jpg")
    thumbnails.fetch("a", "https://example.test/a.jpg")

    assert calls == ["https://example.test/a.jpg", "https://example.test/a.jpg"]
    thumbnails.clear_cache()
