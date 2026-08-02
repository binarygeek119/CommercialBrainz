"""Smoke tests for non-fingerprint background task status helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.background_tasks_status import _latest_dump_info, get_background_tasks_status


def test_latest_dump_info_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    info = _latest_dump_info()
    assert info["available"] is False
    assert info["filename"] is None


def test_latest_dump_info_picks_newest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dumps = Path("dumps")
    dumps.mkdir()
    older = dumps / "commercialbrainz-2020-01-01.json.gz"
    newer = dumps / "commercialbrainz-2026-08-01.json.gz"
    older.write_bytes(b"old")
    newer.write_bytes(b"newer-bytes")
    info = _latest_dump_info()
    assert info["available"] is True
    assert info["filename"] == newer.name
    assert info["size_bytes"] == len(b"newer-bytes")


@pytest.mark.asyncio
async def test_get_background_tasks_status_shape():
    empty_group = MagicMock()
    empty_group.all.return_value = []

    empty_videos = MagicMock()
    empty_videos.scalars.return_value.all.return_value = []

    db = MagicMock()
    db.scalar = AsyncMock(side_effect=[0, 0, None])
    db.execute = AsyncMock(side_effect=[empty_group, empty_videos])

    with (
        patch(
            "app.services.background_tasks_status.get_archive_export_status",
            return_value={"status": "idle"},
        ),
        patch(
            "app.services.background_tasks_status.archive_org_configured",
            return_value=False,
        ),
        patch(
            "app.services.background_tasks_status.get_redis_queue_depth",
            new=AsyncMock(return_value=3),
        ),
        patch(
            "app.services.background_tasks_status._latest_dump_info",
            return_value={"available": False, "filename": None, "size_bytes": None},
        ),
    ):
        payload = await get_background_tasks_status(db)

    assert payload["redis_queue_depth"] == 3
    assert payload["archive_export"]["status"] == "idle"
    assert payload["archive_export"]["configured"] is False
    assert payload["thumbnails"]["active_count"] == 0
    assert "cron" in payload["thumbnails"]
    assert "missing_scan_cron" in payload["thumbnails"]
    assert payload["bulk_submit"]["importing_batches"] == 0
    assert "queued" in payload["bulk_submit"]["items_by_status"]
    assert "cron" in payload["expire_edits"]
    assert "cron" in payload["dumps"]
