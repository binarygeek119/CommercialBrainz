"""Tests for custom thumbnail uploads and YouTube re-grab staging."""

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thumbnail_storage import (
    finalize_staged_thumbnail,
    stage_thumbnail,
    validate_thumbnail_bytes,
)
from app.services.youtube_metadata import fetch_and_stage_youtube_thumbnail

# Minimal valid 1x1 PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_validate_thumbnail_png():
    assert validate_thumbnail_bytes(TINY_PNG) == "image/png"


def test_validate_thumbnail_rejects_text():
    with pytest.raises(ValueError, match="JPEG, PNG, or WebP"):
        validate_thumbnail_bytes(b"not an image" + b"x" * 64)


def test_finalize_staged_thumbnail_uses_unique_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.thumbnail_storage.settings.thumbnail_upload_dir",
        str(tmp_path),
    )
    video_sbid = uuid4()
    staging_file, _preview = stage_thumbnail(TINY_PNG, "image/png")

    # Leave a prior permanent file that should be removed on finalize.
    old = tmp_path / f"{video_sbid}.png"
    old.write_bytes(b"old")

    url = finalize_staged_thumbnail(staging_file, video_sbid)
    assert f"/api/v1/media/thumbnails/{video_sbid}-" in url
    assert url.endswith(".png")
    assert not old.exists()
    finals = list(tmp_path.glob(f"{video_sbid}-*.png"))
    assert len(finals) == 1
    assert finals[0].read_bytes() == TINY_PNG


@pytest.mark.asyncio
async def test_fetch_and_stage_youtube_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.thumbnail_storage.settings.thumbnail_upload_dir",
        str(tmp_path),
    )
    source = "https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg"

    response = MagicMock()
    response.content = TINY_PNG
    response.headers = {"content-type": "image/png"}
    response.raise_for_status = MagicMock()

    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.services.youtube_metadata.fetch_youtube_thumbnail",
            return_value=source,
        ),
        patch("httpx.AsyncClient", return_value=client),
    ):
        staging_file, preview_url, source_url = await fetch_and_stage_youtube_thumbnail(
            "abcdefghijk"
        )

    assert source_url == source
    assert staging_file.endswith(".png")
    assert preview_url.startswith("/api/v1/media/thumbnails/pending/")
    assert (tmp_path / "pending" / staging_file).read_bytes() == TINY_PNG
