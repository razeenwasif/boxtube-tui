"""Fetch and cache YouTube thumbnail images as PIL images.

Thumbnails are rendered by ``textual-image``, which uses the terminal's native
graphics protocol (kitty / sixel) when available and falls back to colored
unicode blocks everywhere else.
"""

from __future__ import annotations

import urllib.request
from io import BytesIO

from PIL import Image as PILImage

_CACHE: dict[str, PILImage.Image] = {}
_PANEL = (24, 24, 30)  # matches the detail-pane background


def placeholder() -> PILImage.Image:
    """A neutral 16:9 frame shown before a thumbnail loads."""
    return PILImage.new("RGB", (320, 180), _PANEL)


def fetch(video_id: str, url: str) -> PILImage.Image:
    """Download a thumbnail (cached by video id). Raises on failure."""
    cached = _CACHE.get(video_id)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
    image = PILImage.open(BytesIO(data))
    image.load()
    image = image.convert("RGB")
    _CACHE[video_id] = image
    return image
