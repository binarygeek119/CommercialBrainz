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
        "duration_sec": _json_safe_number(fp.duration_sec),
        "error_message": fp.error_message,
        "probe": _json_safe_value(fp.probe_data or {}),
    }


def _json_safe_number(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


def _json_safe_value(value):
    if isinstance(value, float):
        return _json_safe_number(value)
    if isinstance(value, dict):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(v) for v in value]
    return value


def format_phash_hex(phash: int | None) -> str | None:
    if phash is None:
        return None
    from app.services.phash import phash_as_unsigned

    return f"{phash_as_unsigned(phash):016x}"


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
