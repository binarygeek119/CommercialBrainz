"""Monthly (and on-demand) YouTube availability checks for public videos."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Commercial, Video, VideoLinkCheckStatus, VideoVisibility
from app.services.youtube_metadata import _run_ytdlp_json
from app.utils import youtube_watch_url

logger = logging.getLogger(__name__)
settings = get_settings()

# Transient / ambiguous probe failures — do not treat as dead links.
_ERROR_HINTS = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "http error 429",
    "http error 5",
    "connection",
    "network",
    "ssl",
)

_PRIVATE_HINTS = ("private video", "this video is private")
_AGE_HINTS = (
    "sign in to confirm your age",
    "age-restricted",
    "age restricted",
    "confirm your age",
)
_DEAD_HINTS = (
    "video unavailable",
    "this video has been removed",
    "has been removed",
    "not available",
    "does not exist",
    "copyright",
    "account associated with this video has been terminated",
    "violating youtube",
    "http error 404",
)


def classify_ytdlp_failure(message: str) -> tuple[VideoLinkCheckStatus, str]:
    """Map yt-dlp stderr to a link-check status."""
    text = (message or "").strip()
    lower = text.lower()
    detail = text[:500] or "yt-dlp failed"

    if any(h in lower for h in _PRIVATE_HINTS):
        return VideoLinkCheckStatus.PRIVATE, detail
    if any(h in lower for h in _AGE_HINTS):
        return VideoLinkCheckStatus.AGE_RESTRICTED, detail
    if any(h in lower for h in _ERROR_HINTS) and not any(h in lower for h in _DEAD_HINTS):
        return VideoLinkCheckStatus.ERROR, detail
    if any(h in lower for h in _DEAD_HINTS):
        return VideoLinkCheckStatus.UNAVAILABLE, detail
    # Unknown hard failure — treat as unavailable so mods can review.
    if re.search(r"error|unavailable|removed|deleted", lower):
        return VideoLinkCheckStatus.UNAVAILABLE, detail
    return VideoLinkCheckStatus.ERROR, detail


def classify_ytdlp_info(info: dict[str, Any]) -> tuple[VideoLinkCheckStatus, str | None]:
    availability = str(info.get("availability") or "").strip().lower()
    if availability in {"private", "needs_auth", "subscriber_only", "premium_only"}:
        return VideoLinkCheckStatus.PRIVATE, f"availability={availability}"
    if "age" in availability:
        return VideoLinkCheckStatus.AGE_RESTRICTED, f"availability={availability}"
    if availability in {"unlisted", "public", "is_public", ""}:
        return VideoLinkCheckStatus.OK, None
    # Unknown availability string with an id still usually means the video exists.
    if info.get("id"):
        return VideoLinkCheckStatus.OK, f"availability={availability or 'unknown'}"
    return VideoLinkCheckStatus.ERROR, f"unexpected availability={availability or 'missing'}"


def probe_youtube_id(youtube_id: str) -> tuple[VideoLinkCheckStatus, str | None]:
    url = youtube_watch_url(youtube_id)
    try:
        info = _run_ytdlp_json(url)
    except Exception as exc:  # noqa: BLE001 — classify any probe failure
        return classify_ytdlp_failure(str(exc))
    return classify_ytdlp_info(info)


def _apply_check_result(
    video: Video,
    status: VideoLinkCheckStatus,
    detail: str | None,
    *,
    now: datetime | None = None,
) -> None:
    checked_at = now or datetime.now(UTC)
    video.link_check_status = status
    video.link_checked_at = checked_at
    video.link_check_detail = detail
    if status in {
        VideoLinkCheckStatus.UNAVAILABLE,
        VideoLinkCheckStatus.PRIVATE,
        VideoLinkCheckStatus.AGE_RESTRICTED,
    }:
        if video.link_flagged_at is None:
            video.link_flagged_at = checked_at
    elif status == VideoLinkCheckStatus.OK:
        video.link_flagged_at = None


async def check_video_link(db: AsyncSession, video: Video) -> VideoLinkCheckStatus:
    status, detail = await asyncio.to_thread(probe_youtube_id, video.youtube_id)
    _apply_check_result(video, status, detail)
    return status


async def check_public_youtube_links(
    db: AsyncSession,
    *,
    limit: int | None = None,
    delay_seconds: float = 0.75,
) -> dict[str, int]:
    """Probe all public videos and flag dead/private/age-restricted links."""
    query = (
        select(Video)
        .where(Video.visibility == VideoVisibility.PUBLIC)
        .order_by(Video.created_at.asc())
    )
    if limit is not None:
        query = query.limit(limit)

    result = await db.execute(query)
    videos = list(result.scalars().all())

    counts = {
        "checked": 0,
        "ok": 0,
        "unavailable": 0,
        "private": 0,
        "age_restricted": 0,
        "error": 0,
        "flagged": 0,
        "candidates": len(videos),
    }

    for index, video in enumerate(videos):
        status = await check_video_link(db, video)
        counts["checked"] += 1
        counts[status.value] = counts.get(status.value, 0) + 1
        if video.link_flagged_at is not None:
            counts["flagged"] += 1

        if (index + 1) % 25 == 0:
            await db.commit()
            logger.info(
                "Link check progress: %d/%d (flagged=%d)",
                index + 1,
                len(videos),
                counts["flagged"],
            )

        if delay_seconds > 0 and index + 1 < len(videos):
            await asyncio.sleep(delay_seconds)

    await db.commit()
    logger.info("Link check finished: %s", counts)
    return counts


async def enqueue_link_check(*, limit: int | None = None) -> None:
    """Queue a public YouTube link scan on the arq worker."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("check_public_youtube_links", limit)
    finally:
        await pool.aclose()


async def list_flagged_dead_links(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[Video]:
    result = await db.execute(
        select(Video)
        .options(selectinload(Video.commercial))
        .where(
            Video.visibility == VideoVisibility.PUBLIC,
            Video.link_flagged_at.is_not(None),
            Video.link_check_status.in_(
                [
                    VideoLinkCheckStatus.UNAVAILABLE,
                    VideoLinkCheckStatus.PRIVATE,
                    VideoLinkCheckStatus.AGE_RESTRICTED,
                ]
            ),
        )
        .order_by(Video.link_flagged_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_flagged_dead_links(db: AsyncSession) -> int:
    value = await db.scalar(
        select(func.count())
        .select_from(Video)
        .where(
            Video.visibility == VideoVisibility.PUBLIC,
            Video.link_flagged_at.is_not(None),
            Video.link_check_status.in_(
                [
                    VideoLinkCheckStatus.UNAVAILABLE,
                    VideoLinkCheckStatus.PRIVATE,
                    VideoLinkCheckStatus.AGE_RESTRICTED,
                ]
            ),
        )
    )
    return value or 0


async def dismiss_dead_link(db: AsyncSession, video_id: UUID) -> Video | None:
    """Clear the flag without changing visibility (mod reviewed / not actionable)."""
    video = await db.get(Video, video_id)
    if not video:
        return None
    video.link_flagged_at = None
    if video.link_check_detail:
        video.link_check_detail = f"Dismissed by moderator. Previous: {video.link_check_detail}"[
            :500
        ]
    else:
        video.link_check_detail = "Dismissed by moderator"
    return video


async def get_video_for_link_check(db: AsyncSession, video_id: UUID) -> Video | None:
    result = await db.execute(
        select(Video)
        .options(selectinload(Video.commercial))
        .where(Video.sbid == video_id)
    )
    return result.scalar_one_or_none()


def flagged_video_to_dict(video: Video) -> dict[str, Any]:
    commercial: Commercial | None = video.commercial
    return {
        "sbid": video.sbid,
        "youtube_id": video.youtube_id,
        "youtube_url": video.youtube_url,
        "commercial_id": video.commercial_id,
        "commercial_title": commercial.title if commercial else None,
        "commercial_sbid": commercial.sbid if commercial else None,
        "link_check_status": video.link_check_status.value if video.link_check_status else None,
        "link_checked_at": video.link_checked_at,
        "link_check_detail": video.link_check_detail,
        "link_flagged_at": video.link_flagged_at,
        "visibility": video.visibility.value,
    }
