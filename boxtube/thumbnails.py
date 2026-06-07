"""Fetch and cache YouTube thumbnail images as PIL images.

Thumbnails are rendered by ``textual-image``, which uses the terminal's native
graphics protocol (kitty / sixel) when available and falls back to colored
unicode blocks everywhere else.
"""

from __future__ import annotations

import os
import urllib.request
from collections import OrderedDict
from io import BytesIO

from PIL import Image as PILImage

_CACHE: OrderedDict[str, PILImage.Image] = OrderedDict()
_PANEL = (24, 24, 30)  # matches the detail-pane background
_DEFAULT_CACHE_SIZE = 64


def cache_size() -> int:
    """Maximum thumbnails to keep in memory."""
    try:
        return max(0, int(os.environ.get("BOXTUBE_THUMB_CACHE_SIZE", _DEFAULT_CACHE_SIZE)))
    except ValueError:
        return _DEFAULT_CACHE_SIZE


def clear_cache() -> None:
    """Empty the in-memory thumbnail cache."""
    _CACHE.clear()


def placeholder() -> PILImage.Image:
    """A neutral 16:9 frame shown before a thumbnail loads."""
    return PILImage.new("RGB", (320, 180), _PANEL)


# Grid cards are small; a downscaled copy re-renders cheaper than the full
# thumbnail (which the larger preview pane keeps using).
CARD_THUMB_WIDTH = 240


def for_card(image: PILImage.Image) -> PILImage.Image:
    """A copy of ``image`` sized for a grid card (cheaper to render)."""
    if image.width <= CARD_THUMB_WIDTH:
        return image
    height = round(CARD_THUMB_WIDTH * image.height / image.width)
    return image.resize((CARD_THUMB_WIDTH, height))


def fetch(video_id: str, url: str) -> PILImage.Image:
    """Download a thumbnail (cached by video id). Raises on failure."""
    cached = _CACHE.get(video_id)
    if cached is not None:
        _CACHE.move_to_end(video_id)
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
    image = PILImage.open(BytesIO(data))
    image.load()
    image = image.convert("RGB")
    max_size = cache_size()
    if max_size == 0:
        return image
    _CACHE[video_id] = image
    _CACHE.move_to_end(video_id)
    while len(_CACHE) > max_size:
        _CACHE.popitem(last=False)
    return image
