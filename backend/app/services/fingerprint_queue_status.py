"""Fingerprint worker queue status for admin/mod dashboards."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FingerprintStatus, MediaFingerprint
from app.services.hash_queue import get_redis_queue_depth


def _fp_to_queue_item(row: MediaFingerprint, *, position: int | None = None) -> dict:
    return {
        "id": row.id,
        "youtube_id": row.youtube_id,
        "phase": row.phase.value,
        "status": row.status.value,
        "edit_id": row.edit_id,
        "video_id": row.video_id,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "error_message": row.error_message,
        "queue_position": position,
    }


async def get_fingerprint_queue_status(db: AsyncSession, *, pending_limit: int = 50) -> dict:
    pending_count = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PENDING)
    ) or 0
    processing_count = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PROCESSING)
    ) or 0

    proc_result = await db.execute(
        select(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PROCESSING)
        .order_by(MediaFingerprint.started_at.asc().nullsfirst())
    )
    processing = [_fp_to_queue_item(r) for r in proc_result.scalars().all()]

    pend_result = await db.execute(
        select(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PENDING)
        .order_by(MediaFingerprint.created_at.asc())
        .limit(pending_limit)
    )
    pending_rows = pend_result.scalars().all()
    pending = [_fp_to_queue_item(r, position=i + 1) for i, r in enumerate(pending_rows)]

    redis_queue_depth = await get_redis_queue_depth()

    return {
        "pending_count": pending_count,
        "processing_count": processing_count,
        "redis_queue_depth": redis_queue_depth,
        "processing": processing,
        "pending": pending,
    }
