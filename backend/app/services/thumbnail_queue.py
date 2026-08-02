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
from app.models import Video, VideoVisibility
from app.services.thumbnail_fetch import (
    ensure_video_thumbnail,
    get_thumbnail_fetch_meta,
    mark_thumbnail_force_refresh,
    needs_force_thumbnail_regrab,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_arq_pool():
    return await create_pool(RedisSettings.from_dsn(settings.redis_url))


async def enqueue_thumbnail_job(video_id: UUID, *, force: bool = False) -> bool:
    try:
        pool = await _get_arq_pool()
        try:
            await pool.enqueue_job("ensure_thumbnail", str(video_id), force)
            return True
        finally:
            await pool.aclose()
    except Exception:
        logger.exception("Failed to enqueue thumbnail job %s", video_id)
        return False


async def ensure_thumbnail(ctx, video_id: str, force: bool = False) -> str:
    async with async_session_factory() as db:
        status = await ensure_video_thumbnail(db, UUID(video_id), force=bool(force))
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
    jobs: list[tuple[UUID, bool]] = []

    async with async_session_factory() as db:
        result = await db.execute(
            select(Video)
            .where(Video.youtube_id.is_not(None))
            .order_by(Video.created_at.desc())
            .limit(200)
        )
        for video in result.scalars().all():
            meta = get_thumbnail_fetch_meta(video)
            status = meta.get("status")
            force = bool(meta.get("force"))
            url = video.thumbnail_url or ""
            # Hosted thumbs are done unless a forced re-grab is still pending.
            if "/api/v1/media/thumbnails/" in url and not force:
                continue
            if status not in {"pending", "retry"}:
                continue
            attempts = int(meta.get("attempts") or 0)
            if attempts >= settings.thumbnail_max_retries and status == "retry":
                # Final attempt should already have run frame extract; skip.
                continue
            last_at = _parse_iso(meta.get("last_attempt_at"))
            if status == "pending" and attempts == 0:
                jobs.append((video.sbid, force))
                continue
            if last_at is None or last_at <= retry_before:
                jobs.append((video.sbid, force))

    for video_id, force in jobs[:20]:
        await enqueue_thumbnail_job(video_id, force=force)
    if jobs:
        logger.info("Queued %d thumbnail fetch job(s)", min(len(jobs), 20))
    return min(len(jobs), 20)


async def scan_missing_thumbnails(ctx, limit: int | None = None) -> dict:
    """
    Find public videos with missing/broken thumbnails and force re-grab them.

    Criteria: empty thumbnail_url, hosted URL with no file on disk, or failed
    fetch past the cooldown. Enqueues at most ``limit`` (or configured batch)
    force jobs per run so the shared worker queue is not flooded.
    """
    batch = (
        limit
        if limit is not None and limit > 0
        else settings.thumbnail_missing_scan_batch
    )
    window = settings.thumbnail_missing_scan_window
    now = datetime.now(UTC)
    to_queue: list[UUID] = []
    candidates = 0
    scanned = 0

    async with async_session_factory() as db:
        result = await db.execute(
            select(Video)
            .where(
                Video.youtube_id.is_not(None),
                Video.visibility == VideoVisibility.PUBLIC,
            )
            # Oldest-updated first so successful re-grabs rotate the window.
            .order_by(Video.updated_at.asc())
            .limit(window)
        )
        videos = list(result.scalars().all())
        scanned = len(videos)
        for video in videos:
            if not needs_force_thumbnail_regrab(video, now=now):
                continue
            candidates += 1
            if len(to_queue) >= batch:
                continue
            try:
                mark_thumbnail_force_refresh(video)
            except ValueError:
                continue
            to_queue.append(video.sbid)
        await db.commit()

    enqueued = 0
    for video_id in to_queue:
        if await enqueue_thumbnail_job(video_id, force=True):
            enqueued += 1

    logger.info(
        "Missing thumbnail scan: scanned=%d candidates=%d enqueued=%d",
        scanned,
        candidates,
        enqueued,
    )
    return {
        "scanned": scanned,
        "candidates": candidates,
        "enqueued": enqueued,
        "queued": enqueued > 0,
    }


async def enqueue_missing_thumbnail_scan(*, limit: int | None = None) -> None:
    """Queue a missing-thumbnail scan on the arq worker."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("scan_missing_thumbnails", limit)
    finally:
        await pool.aclose()
