"""Shared test fixtures."""

from __future__ import annotations

import pytest
from PIL import Image as PILImage

from boxtube.youtube import Video


@pytest.fixture
def sample_videos() -> list[Video]:
    """A couple of representative results, including edge cases."""
    return [
        Video(
            id="dQw4w9WgXcQ",
            title="Never Gonna Give You Up [HD]",
            channel="Rick Astley",
            duration=213,
            views=1_600_000_000,
            description="The official video. [Remastered]",
        ),
        Video(
            id="abcd1234567",
            title="lofi hip hop radio",
            channel="Lofi Girl",
            duration=None,
            views=None,
            description="",
        ),
    ]


@pytest.fixture
def fake_image() -> PILImage.Image:
    """A small non-flat image standing in for a downloaded thumbnail."""
    img = PILImage.new("RGB", (320, 180))
    for x in range(320):
        for y in range(180):
            img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    return img
