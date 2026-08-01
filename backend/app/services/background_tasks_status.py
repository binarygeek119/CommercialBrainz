"""Aggregate non-fingerprint background task status for mod/admin dashboards."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BulkSubmissionBatch,
    BulkSubmissionBatchStatus,
    BulkSubmissionItem,
    BulkSubmissionItemStatus,
    Video,
    VideoLinkCheckStatus,
)
from app.services.archive_export_queue import get_archive_export_status
from app.services.archive_org_upload import archive_org_configured
from app.services.hash_queue import get_redis_queue_depth
from app.services.thumbnail_fetch import THUMB_META_KEY


async def _count_bulk_items_by_status(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(BulkSubmissionItem.status, func.count())
        .select_from(BulkSubmissionItem)
        .group_by(BulkSubmissionItem.status)
    )
    counts = {status.value: 0 for status in BulkSubmissionItemStatus}
    for status, count in result.all():
        counts[status.value] = int(count)
    return counts


async def _thumbnail_counts(db: AsyncSession) -> dict:
    """Count videos with pending/retry thumbnail fetch meta (scan recent rows)."""
    pending = 0
    retry = 0
    failed = 0
    sample: list[dict] = []

    result = await db.execute(
        select(Video)
        .where(Video.youtube_id.is_not(None))
        .order_by(Video.updated_at.desc())
        .limit(500)
    )
    for video in result.scalars().all():
        extra = video.extra_data or {}
        meta = extra.get(THUMB_META_KEY)
        if not isinstance(meta, dict):
            continue
        status = meta.get("status")
        if status == "pending":
            pending += 1
        elif status == "retry":
            retry += 1
        elif status == "failed":
            failed += 1
        else:
            continue
        if len(sample) < 15:
            sample.append(
                {
                    "video_id": video.sbid,
                    "youtube_id": video.youtube_id,
                    "status": status,
                    "attempts": int(meta.get("attempts") or 0),
                    "last_error": meta.get("last_error"),
                    "last_attempt_at": meta.get("last_attempt_at"),
                    "force": bool(meta.get("force")),
                }
            )

    return {
        "pending_count": pending,
        "retry_count": retry,
        "failed_count": failed,
        "active_count": pending + retry,
        "sample": sample,
    }


def _latest_dump_info() -> dict:
    dumps_dir = Path("dumps")
    if not dumps_dir.exists():
        return {"available": False, "filename": None, "size_bytes": None}
    files = sorted(dumps_dir.glob("commercialbrainz-*.json.gz"), reverse=True)
    if not files:
        return {"available": False, "filename": None, "size_bytes": None}
    latest = files[0]
    return {
        "available": True,
        "filename": latest.name,
        "size_bytes": latest.stat().st_size,
    }


async def get_background_tasks_status(db: AsyncSession) -> dict:
    importing_batches = await db.scalar(
        select(func.count())
        .select_from(BulkSubmissionBatch)
        .where(BulkSubmissionBatch.status == BulkSubmissionBatchStatus.IMPORTING)
    ) or 0

    bulk_items = await _count_bulk_items_by_status(db)
    bulk_active = (
        bulk_items.get("queued", 0)
        + bulk_items.get("pending_meta", 0)
        + bulk_items.get("hashing", 0)
    )

    flagged_links = await db.scalar(
        select(func.count())
        .select_from(Video)
        .where(
            Video.link_check_status.in_(
                [
                    VideoLinkCheckStatus.UNAVAILABLE,
                    VideoLinkCheckStatus.PRIVATE,
                    VideoLinkCheckStatus.AGE_RESTRICTED,
                    VideoLinkCheckStatus.ERROR,
                ]
            ),
            Video.link_flagged_at.is_not(None),
        )
    ) or 0

    last_link_check = await db.scalar(select(func.max(Video.link_checked_at)))

    archive = get_archive_export_status()
    archive["configured"] = archive_org_configured()

    thumbnails = await _thumbnail_counts(db)
    redis_queue_depth = await get_redis_queue_depth()

    return {
        "redis_queue_depth": redis_queue_depth,
        "worker_max_jobs": 1,
        "note": (
            "Fingerprinting has its own tab. All ARQ jobs (including fingerprints) "
            "share one worker queue (max_jobs=1)."
        ),
        "archive_export": {
            "status": archive.get("status") or "idle",
            "configured": bool(archive.get("configured")),
            "stage": archive.get("stage"),
            "started_at": archive.get("started_at"),
            "finished_at": archive.get("finished_at"),
            "error": archive.get("error"),
            "identifier": archive.get("identifier"),
            "item_url": archive.get("item_url"),
        },
        "thumbnails": thumbnails,
        "bulk_submit": {
            "importing_batches": importing_batches,
            "active_items": bulk_active,
            "items_by_status": bulk_items,
        },
        "link_check": {
            "flagged_count": flagged_links,
            "last_checked_at": last_link_check.isoformat() if last_link_check else None,
            "cron": "Monthly on day 1 at 04:00 UTC (or triggered from Dead links)",
        },
        "dumps": {
            **_latest_dump_info(),
            "cron": "Daily at 02:00 UTC",
        },
        "expire_edits": {
            "cron": "Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)",
        },
    }
