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
from PIL import ImageDraw, ImageFont

_CACHE: OrderedDict[str, PILImage.Image] = OrderedDict()
_PANEL = (24, 24, 30)  # matches the detail-pane background
_DEFAULT_CACHE_SIZE = 64
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


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
    return image.resize((CARD_THUMB_WIDTH, height), PILImage.LANCZOS)


def _badge_font(px: int):
    """A bold font at ~``px`` pixels, cached. Falls back gracefully."""
    px = max(8, px)
    font = _FONT_CACHE.get(px)
    if font is not None:
        return font
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial.ttf"):
        try:
            font = ImageFont.truetype(name, px)
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(px)  # Pillow >= 10.1 scales the default
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[px] = font
    return font


def with_duration_badge(image: PILImage.Image, text: str) -> PILImage.Image:
    """Return a copy of ``image`` with a YouTube-style duration pill, bottom-right.

    The badge is baked into the pixels so it renders on every image backend
    (sixel / kitty / half-block). ``text`` like ``"12:34"``; ``"—"``/empty is a
    no-op (live streams, unknown durations).
    """
    if not text or text == "—":
        return image
    img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(img, "RGBA")
    px = max(9, img.height // 9)
    font = _badge_font(px)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    pad = max(2, px // 3)
    margin = max(2, px // 4)
    bw, bh = tw + 2 * pad, th + 2 * pad
    x0 = img.width - bw - margin
    y0 = img.height - bh - margin
    draw.rounded_rectangle(
        [x0, y0, x0 + bw, y0 + bh], radius=max(2, px // 5), fill=(0, 0, 0, 200)
    )
    draw.text((x0 + pad - left, y0 + pad - top), text, font=font, fill=(255, 255, 255, 255))
    return img


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
