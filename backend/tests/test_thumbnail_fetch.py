"""Tests for YouTube thumbnail fetch / frame fallback helpers."""

from __future__ import annotations

import random
from io import BytesIO
from uuid import uuid4

from PIL import Image

from app.services.thumbnail_fetch import (
    _is_usable_image,
    padded_random_timestamp,
)
from app.services.thumbnail_storage import save_video_thumbnail, validate_thumbnail_bytes


def _jpeg_bytes(width: int = 320, height: int = 180, color=(40, 120, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    # Add noise so it is not a solid-color placeholder.
    for x in range(0, width, 17):
        for y in range(0, height, 13):
            img.putpixel((x, y), ((x * 3) % 255, (y * 5) % 255, 90))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _solid_jpeg(width: int = 480, height: int = 360, color=(128, 128, 128)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_padded_random_timestamp_stays_inside_padded_window():
    rng = random.Random(42)
    duration = 100.0
    for _ in range(50):
        ts = padded_random_timestamp(duration, pad_ratio=0.05, pad_seconds=2.0, rng=rng)
        assert 5.0 <= ts <= 95.0


def test_padded_random_timestamp_short_clip():
    rng = random.Random(7)
    ts = padded_random_timestamp(3.0, pad_ratio=0.05, pad_seconds=2.0, rng=rng)
    assert 0.0 <= ts <= 3.0


def test_is_usable_image_accepts_real_jpeg():
    assert _is_usable_image(_jpeg_bytes())


def test_is_usable_image_rejects_tiny_and_solid():
    assert not _is_usable_image(b"not-an-image" + b"x" * 100)
    assert not _is_usable_image(_solid_jpeg())
    tiny = Image.new("RGB", (8, 8), (10, 20, 30))
    buf = BytesIO()
    tiny.save(buf, format="JPEG")
    assert not _is_usable_image(buf.getvalue())


def test_save_video_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    try:
        video_id = uuid4()
        data = _jpeg_bytes()
        url = save_video_thumbnail(video_id, data, "image/jpeg")
        assert url.endswith(f"{video_id}.jpg")
        assert (tmp_path / f"{video_id}.jpg").is_file()
        assert validate_thumbnail_bytes(data) == "image/jpeg"
    finally:
        get_settings.cache_clear()
