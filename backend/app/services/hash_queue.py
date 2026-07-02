"""Enqueue and finalize media fingerprint jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models import (
    FingerprintPhase,
    FingerprintStatus,
    MediaFingerprint,
)
from app.services.media_hash import run_fingerprint_job

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_arq_pool():
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def get_redis_queue_depth() -> int:
    """Number of jobs waiting in the arq Redis queue."""
    try:
        pool = await _get_arq_pool()
        try:
            return int(await pool.zcard(pool.default_queue_name) or 0)
        finally:
            await pool.aclose()
    except Exception:
        logger.exception("Failed to read Redis queue depth")
        return 0


async def enqueue_hash_job(fingerprint_id: UUID) -> None:
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("hash_media", str(fingerprint_id))
        await pool.aclose()
    except Exception:
        logger.exception("Failed to enqueue hash job %s", fingerprint_id)


async def create_preview_fingerprint(edit_id: UUID, youtube_id: str) -> MediaFingerprint:
    async with async_session_factory() as db:
        fp = MediaFingerprint(
            edit_id=edit_id,
            youtube_id=youtube_id,
            phase=FingerprintPhase.PREVIEW,
            status=FingerprintStatus.PENDING,
        )
        db.add(fp)
        await db.commit()
        await db.refresh(fp)
        fingerprint_id = fp.id

    await enqueue_hash_job(fingerprint_id)
    return fp


async def process_pending_queue(ctx) -> int:
    """Enqueue pending fingerprint jobs and retry eligible failures (cron safety net)."""
    stale_before = datetime.now(UTC) - timedelta(minutes=30)
    retry_before = datetime.now(UTC) - timedelta(minutes=settings.fingerprint_retry_delay_minutes)
    count = 0
    retry_ids: list[UUID] = []
    async with async_session_factory() as db:
        result = await db.execute(
            select(MediaFingerprint.id).where(
                MediaFingerprint.status == FingerprintStatus.PENDING,
            ).order_by(MediaFingerprint.created_at).limit(20)
        )
        pending_ids = [row[0] for row in result.all()]

        stale_result = await db.execute(
            select(MediaFingerprint.id).where(
                MediaFingerprint.status == FingerprintStatus.PROCESSING,
                MediaFingerprint.started_at < stale_before,
            )
        )
        stale_ids = [row[0] for row in stale_result.all()]

        failed_result = await db.execute(
            select(MediaFingerprint.id).where(
                MediaFingerprint.status == FingerprintStatus.FAILED,
                MediaFingerprint.retry_count < settings.fingerprint_max_retries,
                MediaFingerprint.completed_at.is_not(None),
                MediaFingerprint.completed_at < retry_before,
            ).order_by(MediaFingerprint.completed_at).limit(10)
        )
        failed_ids = [row[0] for row in failed_result.all()]

        for fp_id in stale_ids + failed_ids:
            fp = await db.get(MediaFingerprint, fp_id)
            if not fp:
                continue
            fp.status = FingerprintStatus.PENDING
            fp.started_at = None
            if fp_id in failed_ids:
                retry_ids.append(fp_id)
                if fp.video_id:
                    from app.models import Video, VideoHashStatus

                    video = await db.get(Video, fp.video_id)
                    if video:
                        video.hash_status = VideoHashStatus.PENDING
        await db.commit()

    for fp_id in pending_ids + stale_ids + failed_ids:
        await enqueue_hash_job(fp_id)
        count += 1
    if retry_ids:
        logger.info("Re-queued %d failed fingerprint job(s) for retry", len(retry_ids))
    return count


async def hash_media(ctx, fingerprint_id: str) -> str:
    await run_fingerprint_job(UUID(fingerprint_id))
    return fingerprint_id
