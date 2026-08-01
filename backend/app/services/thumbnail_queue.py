"""Enqueue and retry YouTube thumbnail verification jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models import Video
from app.services.thumbnail_fetch import ensure_video_thumbnail, get_thumbnail_fetch_meta

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_arq_pool():
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def enqueue_thumbnail_job(video_id: UUID) -> None:
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("ensure_thumbnail", str(video_id))
        await pool.aclose()
    except Exception:
        logger.exception("Failed to enqueue thumbnail job %s", video_id)


async def ensure_thumbnail(ctx, video_id: str) -> str:
    async with async_session_factory() as db:
        status = await ensure_video_thumbnail(db, UUID(video_id))
        await db.commit()
    return status


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def process_thumbnail_retries(ctx) -> int:
    """Re-queue videos whose YouTube thumbnail fetch is pending/retryable."""
    retry_before = datetime.now(UTC) - timedelta(minutes=settings.thumbnail_retry_delay_minutes)
    ids: list[UUID] = []

    async with async_session_factory() as db:
        result = await db.execute(
            select(Video)
            .where(Video.youtube_id.is_not(None))
            .order_by(Video.created_at.desc())
            .limit(200)
        )
        for video in result.scalars().all():
            url = video.thumbnail_url or ""
            if "/api/v1/media/thumbnails/" in url:
                continue
            meta = get_thumbnail_fetch_meta(video)
            status = meta.get("status")
            if status not in {"pending", "retry"}:
                continue
            attempts = int(meta.get("attempts") or 0)
            if attempts >= settings.thumbnail_max_retries and status == "retry":
                # Final attempt should already have run frame extract; skip.
                continue
            last_at = _parse_iso(meta.get("last_attempt_at"))
            if status == "pending" and attempts == 0:
                ids.append(video.sbid)
                continue
            if last_at is None or last_at <= retry_before:
                ids.append(video.sbid)

    for video_id in ids[:20]:
        await enqueue_thumbnail_job(video_id)
    if ids:
        logger.info("Queued %d thumbnail fetch job(s)", min(len(ids), 20))
    return min(len(ids), 20)
