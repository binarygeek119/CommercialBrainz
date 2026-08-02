"""Tests for YouTube thumbnail fetch / frame fallback helpers."""

from __future__ import annotations

import random
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from app.services.thumbnail_fetch import (
    _is_usable_image,
    ensure_video_thumbnail,
    mark_thumbnail_force_refresh,
    needs_force_thumbnail_regrab,
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
        assert url.startswith(f"/api/v1/media/thumbnails/{video_id}-")
        assert url.endswith(".jpg")
        finals = list(tmp_path.glob(f"{video_id}-*.jpg"))
        assert len(finals) == 1
        assert validate_thumbnail_bytes(data) == "image/jpeg"
    finally:
        get_settings.cache_clear()


def test_mark_thumbnail_force_refresh_resets_hosted_url():
    video = SimpleNamespace(
        youtube_id="5uaYHYs4ubw",
        thumbnail_url="/api/v1/media/thumbnails/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg",
        extra_data={},
    )
    mark_thumbnail_force_refresh(video)
    # Keep the current URL visible while the worker streams a new frame.
    assert video.thumbnail_url.startswith("/api/v1/media/thumbnails/")
    meta = video.extra_data["thumbnail_fetch"]
    assert meta["status"] == "pending"
    assert meta["force"] is True
    assert meta["attempts"] == 0


def test_mark_thumbnail_force_refresh_requires_youtube_id():
    video = SimpleNamespace(youtube_id=None, thumbnail_url=None, extra_data={})
    with pytest.raises(ValueError, match="YouTube"):
        mark_thumbnail_force_refresh(video)


def test_needs_force_thumbnail_regrab_empty_url():
    video = SimpleNamespace(
        youtube_id="abc12345678",
        thumbnail_url=None,
        extra_data={},
    )
    assert needs_force_thumbnail_regrab(video) is True


def test_needs_force_thumbnail_regrab_skips_pending():
    video = SimpleNamespace(
        youtube_id="abc12345678",
        thumbnail_url=None,
        extra_data={"thumbnail_fetch": {"status": "pending", "force": True}},
    )
    assert needs_force_thumbnail_regrab(video) is False


def test_needs_force_thumbnail_regrab_missing_hosted_file(tmp_path, monkeypatch):
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()
    try:
        video_id = uuid4()
        video = SimpleNamespace(
            youtube_id="abc12345678",
            thumbnail_url=f"/api/v1/media/thumbnails/{video_id}.jpg",
            extra_data={"thumbnail_fetch": {"status": "ok"}},
        )
        assert needs_force_thumbnail_regrab(video) is True

        # Create the file — should no longer need a re-grab.
        (tmp_path / f"{video_id}.jpg").write_bytes(_jpeg_bytes())
        assert needs_force_thumbnail_regrab(video) is False
    finally:
        get_settings.cache_clear()


def test_needs_force_thumbnail_regrab_leaves_healthy_cdn_alone():
    video = SimpleNamespace(
        youtube_id="abc12345678",
        thumbnail_url="https://i.ytimg.com/vi/abc12345678/hqdefault.jpg",
        extra_data={"thumbnail_fetch": {"status": "ok", "source": "youtube_cdn"}},
    )
    assert needs_force_thumbnail_regrab(video) is False


def test_needs_force_thumbnail_regrab_failed_respects_cooldown(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app.config import get_settings
    from app.services import thumbnail_fetch as tf

    get_settings.cache_clear()
    tf.settings = get_settings()
    monkeypatch.setattr(tf.settings, "thumbnail_missing_scan_cooldown_hours", 6)

    now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    recent = (now - timedelta(hours=1)).isoformat()
    old = (now - timedelta(hours=7)).isoformat()

    recent_fail = SimpleNamespace(
        youtube_id="abc12345678",
        thumbnail_url="https://i.ytimg.com/vi/abc12345678/hqdefault.jpg",
        extra_data={
            "thumbnail_fetch": {"status": "failed", "last_attempt_at": recent},
        },
    )
    assert needs_force_thumbnail_regrab(recent_fail, now=now) is False

    old_fail = SimpleNamespace(
        youtube_id="abc12345678",
        thumbnail_url="https://i.ytimg.com/vi/abc12345678/hqdefault.jpg",
        extra_data={
            "thumbnail_fetch": {"status": "failed", "last_attempt_at": old},
        },
    )
    assert needs_force_thumbnail_regrab(old_fail, now=now) is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_scan_missing_thumbnails_marks_and_enqueues(tmp_path, monkeypatch):
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_queue as tq
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()
    tq.settings = get_settings()
    monkeypatch.setattr(tq.settings, "thumbnail_missing_scan_batch", 5)
    monkeypatch.setattr(tq.settings, "thumbnail_missing_scan_window", 50)

    video_id = uuid4()
    video = SimpleNamespace(
        sbid=video_id,
        youtube_id="abc12345678",
        thumbnail_url=None,
        visibility="public",
        updated_at=None,
        extra_data={},
    )

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [video]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    try:
        with (
            patch.object(tq, "async_session_factory", return_value=session_cm),
            patch.object(tq, "enqueue_thumbnail_job", new=AsyncMock(return_value=True)) as enqueue,
        ):
            summary = await tq.scan_missing_thumbnails({}, limit=5)

        assert summary["scanned"] == 1
        assert summary["candidates"] == 1
        assert summary["enqueued"] == 1
        assert video.extra_data["thumbnail_fetch"]["force"] is True
        assert video.extra_data["thumbnail_fetch"]["status"] == "pending"
        enqueue.assert_awaited_once_with(video_id, force=True)
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ensure_video_thumbnail_force_extracts_frame(tmp_path, monkeypatch):
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()

    video_id = uuid4()
    video = SimpleNamespace(
        sbid=video_id,
        youtube_id="5uaYHYs4ubw",
        thumbnail_url="https://i.ytimg.com/vi/5uaYHYs4ubw/hqdefault.jpg",
        duration_ms=30000,
        extra_data={"thumbnail_fetch": {"status": "pending", "attempts": 0, "force": True}},
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=video)
    db.flush = AsyncMock()

    frame = _jpeg_bytes()
    try:
        with (
            patch.object(tf, "download_cdn_thumbnail", return_value=_jpeg_bytes()) as cdn,
            patch.object(tf, "extract_random_frame_jpeg", return_value=frame) as extract,
        ):
            status = await ensure_video_thumbnail(db, video_id, force=True)
        assert status == "ok"
        extract.assert_called_once()
        cdn.assert_not_called()
        assert f"/api/v1/media/thumbnails/{video_id}-" in video.thumbnail_url
        assert video.extra_data["thumbnail_fetch"]["source"] == "extracted_frame"
        assert video.extra_data["thumbnail_fetch"]["force"] is False
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ensure_video_thumbnail_force_falls_back_to_cdn(tmp_path, monkeypatch):
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()

    video_id = uuid4()
    video = SimpleNamespace(
        sbid=video_id,
        youtube_id="5uaYHYs4ubw",
        thumbnail_url="https://i.ytimg.com/vi/5uaYHYs4ubw/hqdefault.jpg",
        duration_ms=30000,
        extra_data={"thumbnail_fetch": {"status": "pending", "attempts": 0, "force": True}},
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=video)
    db.flush = AsyncMock()

    try:
        with (
            patch.object(
                tf, "extract_random_frame_jpeg", side_effect=RuntimeError("no stream")
            ),
            patch.object(tf, "download_cdn_thumbnail", return_value=_jpeg_bytes()),
        ):
            status = await ensure_video_thumbnail(db, video_id, force=True)
        assert status == "ok"
        assert f"/api/v1/media/thumbnails/{video_id}-" in video.thumbnail_url
        assert video.extra_data["thumbnail_fetch"]["source"] == "youtube_cdn_hosted"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ensure_video_thumbnail_force_falls_back_to_frame(tmp_path, monkeypatch):
    """Non-force third attempt still extracts a frame when CDN fails."""
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()
    monkeypatch.setattr(tf.settings, "thumbnail_max_retries", 1)

    video_id = uuid4()
    video = SimpleNamespace(
        sbid=video_id,
        youtube_id="5uaYHYs4ubw",
        thumbnail_url="https://i.ytimg.com/vi/5uaYHYs4ubw/hqdefault.jpg",
        duration_ms=30000,
        extra_data={"thumbnail_fetch": {"status": "retry", "attempts": 0, "force": False}},
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=video)
    db.flush = AsyncMock()

    frame = _jpeg_bytes()
    try:
        with (
            patch.object(tf, "download_cdn_thumbnail", return_value=None),
            patch.object(tf, "extract_random_frame_jpeg", return_value=frame) as extract,
        ):
            status = await ensure_video_thumbnail(db, video_id, force=False)
        assert status == "exhausted_frame"
        extract.assert_called_once()
        assert f"/api/v1/media/thumbnails/{video_id}-" in video.thumbnail_url
        assert video.extra_data["thumbnail_fetch"]["source"] == "extracted_frame"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ensure_video_thumbnail_force_hosts_cdn_image(tmp_path, monkeypatch):
    """Legacy name kept: force CDN host path is the fallback after frame failure."""
    monkeypatch.setenv("THUMBNAIL_UPLOAD_DIR", str(tmp_path))
    from app.config import get_settings
    from app.services import thumbnail_fetch as tf
    from app.services import thumbnail_storage as ts

    get_settings.cache_clear()
    ts.settings = get_settings()
    tf.settings = get_settings()

    video_id = uuid4()
    video = SimpleNamespace(
        sbid=video_id,
        youtube_id="5uaYHYs4ubw",
        thumbnail_url="https://i.ytimg.com/vi/5uaYHYs4ubw/hqdefault.jpg",
        duration_ms=30000,
        extra_data={"thumbnail_fetch": {"status": "pending", "attempts": 0, "force": True}},
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=video)
    db.flush = AsyncMock()

    try:
        with (
            patch.object(
                tf, "extract_random_frame_jpeg", side_effect=RuntimeError("boom")
            ),
            patch.object(tf, "download_cdn_thumbnail", return_value=_jpeg_bytes()),
        ):
            status = await ensure_video_thumbnail(db, video_id, force=True)
        assert status == "ok"
        assert f"/api/v1/media/thumbnails/{video_id}-" in video.thumbnail_url
        assert video.extra_data["thumbnail_fetch"]["source"] == "youtube_cdn_hosted"
    finally:
        get_settings.cache_clear()
