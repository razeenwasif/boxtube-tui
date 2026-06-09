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


def test_duration_badge_paints_without_mutating_source():
    src = PILImage.new("RGB", (240, 135), (20, 20, 20))
    out = thumbnails.with_duration_badge(src, "12:34")
    assert out.size == src.size
    assert out is not src
    # Source is untouched (cache safety); badge changed some bottom-right pixels.
    assert src.getpixel((230, 128)) == (20, 20, 20)
    assert out.getpixel((230, 128)) != (20, 20, 20)


def test_fetch_bounds_oversized_images(monkeypatch):
    thumbnails.clear_cache()
    buf = BytesIO()
    PILImage.new("RGB", (720, 1280), (10, 10, 10)).save(buf, format="JPEG")
    data = buf.getvalue()
    monkeypatch.setattr(
        thumbnails.urllib.request, "urlopen", lambda req, timeout=10: _Response(data)
    )
    img = thumbnails.fetch("vert", "https://example.test/v.jpg")
    assert max(img.size) == 640  # capped to _MAX_CACHE_DIM
    assert img.height > img.width  # vertical aspect preserved
    thumbnails.clear_cache()


def test_duration_badge_noop_for_unknown():
    src = PILImage.new("RGB", (240, 135), (20, 20, 20))
    assert thumbnails.with_duration_badge(src, "—") is src
    assert thumbnails.with_duration_badge(src, "") is src


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
