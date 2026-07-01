"""Query helpers for fingerprint display and duplicate detection."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import FingerprintPhase, MediaFingerprint, Video
from app.services.phash import hamming_distance

settings = get_settings()


async def get_preview_fingerprint(db: AsyncSession, edit_id: UUID) -> MediaFingerprint | None:
    result = await db.execute(
        select(MediaFingerprint)
        .where(MediaFingerprint.edit_id == edit_id, MediaFingerprint.phase == FingerprintPhase.PREVIEW)
        .order_by(MediaFingerprint.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def fingerprint_to_dict(fp: MediaFingerprint | None) -> dict | None:
    if not fp:
        return None
    return {
        "status": fp.status.value,
        "phash": format_phash_hex(fp.phash) if fp.phash is not None else None,
        "file_sha256": fp.file_sha256,
        "audio_fingerprint": fp.audio_fingerprint,
        "duration_sec": fp.duration_sec,
        "error_message": fp.error_message,
    }


def format_phash_hex(phash: int | None) -> str | None:
    if phash is None:
        return None
    return f"{phash & 0xFFFFFFFFFFFFFFFF:016x}"


async def find_phash_duplicates(
    db: AsyncSession,
    phash: int,
    *,
    exclude_video_id: UUID | None = None,
    threshold: int | None = None,
) -> list[dict]:
    limit = threshold if threshold is not None else settings.phash_duplicate_threshold
    result = await db.execute(select(Video).where(Video.phash.is_not(None)))
    matches: list[dict] = []
    for video in result.scalars().all():
        if exclude_video_id and video.sbid == exclude_video_id:
            continue
        if video.phash is None:
            continue
        distance = hamming_distance(phash, video.phash)
        if distance <= limit:
            matches.append(
                {
                    "video_sbid": str(video.sbid),
                    "youtube_id": video.youtube_id,
                    "phash": format_phash_hex(video.phash),
                    "hamming_distance": distance,
                }
            )
    matches.sort(key=lambda m: m["hamming_distance"])
    return matches
