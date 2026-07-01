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
    """Enqueue pending fingerprint jobs (cron safety net)."""
    stale_before = datetime.now(UTC) - timedelta(minutes=30)
    count = 0
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

        for fp_id in stale_ids:
            fp = await db.get(MediaFingerprint, fp_id)
            if fp:
                fp.status = FingerprintStatus.PENDING
                fp.started_at = None
        await db.commit()

    for fp_id in pending_ids + stale_ids:
        await enqueue_hash_job(fp_id)
        count += 1
    return count


async def hash_media(ctx, fingerprint_id: str) -> str:
    await run_fingerprint_job(UUID(fingerprint_id))
    return fingerprint_id
