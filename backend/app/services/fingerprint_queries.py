"""Query helpers for fingerprint display and hash lookups."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import FingerprintPhase, MediaFingerprint, Video, VideoVisibility
from app.services.phash import hamming_distance, phash_to_db

settings = get_settings()

HASH_TYPES = ("phash", "file_sha256", "audio_fingerprint")

_PHASH_HEX_RE = re.compile(r"^[0-9a-fA-F]{1,16}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


async def get_preview_fingerprint(db: AsyncSession, edit_id: UUID) -> MediaFingerprint | None:
    result = await db.execute(
        select(MediaFingerprint)
        .where(
            MediaFingerprint.edit_id == edit_id,
            MediaFingerprint.phase == FingerprintPhase.PREVIEW,
        )
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


def parse_phash_hex(value: str) -> int:
    """Parse a hex pHash string into the signed BIGINT form stored in Postgres."""
    text = (value or "").strip().lower().removeprefix("0x")
    if not _PHASH_HEX_RE.fullmatch(text):
        raise ValueError("phash must be 1–16 hexadecimal digits")
    return phash_to_db(int(text, 16))


def normalize_file_sha256(value: str) -> str:
    text = (value or "").strip().lower().removeprefix("0x")
    if not _SHA256_HEX_RE.fullmatch(text):
        raise ValueError("file_sha256 must be a 64-character hexadecimal digest")
    return text


def video_hash_match_dict(
    video: Video,
    *,
    match_type: str,
    hamming_distance: int | None = None,
) -> dict:
    return {
        "video_sbid": str(video.sbid),
        "youtube_id": video.youtube_id,
        "commercial_id": str(video.commercial_id),
        "match_type": match_type,
        "phash": format_phash_hex(video.phash),
        "file_sha256": video.file_sha256,
        "audio_fingerprint": video.audio_fingerprint,
        "hamming_distance": hamming_distance,
        "visibility": video.visibility.value,
    }


def video_hashes_dict(video: Video) -> dict:
    """Serialize all stored hash fields for a video."""
    return {
        "sbid": video.sbid,
        "youtube_id": video.youtube_id,
        "commercial_id": video.commercial_id,
        "phash": format_phash_hex(video.phash),
        "file_sha256": video.file_sha256,
        "audio_fingerprint": video.audio_fingerprint,
        "hash_status": video.hash_status.value if video.hash_status else None,
        "hashed_at": video.hashed_at,
        "visibility": video.visibility.value,
    }


async def get_video_hashes_by_sbid(
    db: AsyncSession,
    sbid: UUID,
    *,
    public_only: bool = True,
) -> Video | None:
    result = await db.execute(
        select(Video).where(Video.sbid == sbid, *_visibility_filter(public_only=public_only))
    )
    return result.scalar_one_or_none()


async def get_video_hashes_by_youtube_id(
    db: AsyncSession,
    youtube_id: str,
    *,
    public_only: bool = True,
) -> Video | None:
    value = (youtube_id or "").strip()
    if not value:
        raise ValueError("youtube_id must not be empty")
    result = await db.execute(
        select(Video).where(
            Video.youtube_id == value,
            *_visibility_filter(public_only=public_only),
        )
    )
    return result.scalar_one_or_none()


async def list_video_hashes(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    hashed_only: bool = False,
    public_only: bool = True,
) -> tuple[list[Video], int]:
    filters = list(_visibility_filter(public_only=public_only))
    if hashed_only:
        filters.append(
            or_(
                Video.phash.is_not(None),
                Video.file_sha256.is_not(None),
                Video.audio_fingerprint.is_not(None),
            )
        )
    count_stmt = select(func.count()).select_from(Video)
    stmt = select(Video)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(Video.created_at.asc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


def _visibility_filter(*, public_only: bool):
    if public_only:
        return (Video.visibility == VideoVisibility.PUBLIC,)
    return ()


async def find_phash_duplicates(
    db: AsyncSession,
    phash: int,
    *,
    exclude_video_id: UUID | None = None,
    threshold: int | None = None,
    public_only: bool = True,
) -> list[dict]:
    limit = threshold if threshold is not None else settings.phash_duplicate_threshold
    result = await db.execute(
        select(Video).where(Video.phash.is_not(None), *_visibility_filter(public_only=public_only))
    )
    matches: list[dict] = []
    for video in result.scalars().all():
        if exclude_video_id and video.sbid == exclude_video_id:
            continue
        if video.phash is None:
            continue
        distance = hamming_distance(phash, video.phash)
        if distance <= limit:
            matches.append(
                video_hash_match_dict(
                    video,
                    match_type="phash",
                    hamming_distance=distance,
                )
            )
    matches.sort(key=lambda m: m["hamming_distance"] if m["hamming_distance"] is not None else 999)
    return matches


async def find_file_sha256_matches(
    db: AsyncSession,
    file_sha256: str,
    *,
    exclude_video_id: UUID | None = None,
    public_only: bool = True,
) -> list[dict]:
    digest = normalize_file_sha256(file_sha256)
    result = await db.execute(
        select(Video).where(
            Video.file_sha256 == digest,
            *_visibility_filter(public_only=public_only),
        )
    )
    matches: list[dict] = []
    for video in result.scalars().all():
        if exclude_video_id and video.sbid == exclude_video_id:
            continue
        matches.append(video_hash_match_dict(video, match_type="file_sha256"))
    return matches


async def find_audio_fingerprint_matches(
    db: AsyncSession,
    audio_fingerprint: str,
    *,
    exclude_video_id: UUID | None = None,
    public_only: bool = True,
) -> list[dict]:
    value = (audio_fingerprint or "").strip()
    if not value:
        raise ValueError("audio_fingerprint must not be empty")
    result = await db.execute(
        select(Video).where(
            Video.audio_fingerprint == value,
            *_visibility_filter(public_only=public_only),
        )
    )
    matches: list[dict] = []
    for video in result.scalars().all():
        if exclude_video_id and video.sbid == exclude_video_id:
            continue
        matches.append(video_hash_match_dict(video, match_type="audio_fingerprint"))
    return matches


async def lookup_videos_by_hash(
    db: AsyncSession,
    *,
    phash: str | None = None,
    file_sha256: str | None = None,
    audio_fingerprint: str | None = None,
    threshold: int | None = None,
    exclude_video_id: UUID | None = None,
    public_only: bool = True,
) -> list[dict]:
    """Look up videos by exactly one hash type."""
    provided = [
        name
        for name, value in (
            ("phash", phash),
            ("file_sha256", file_sha256),
            ("audio_fingerprint", audio_fingerprint),
        )
        if value is not None and str(value).strip() != ""
    ]
    if len(provided) != 1:
        raise ValueError(
            "Provide exactly one of: phash, file_sha256, audio_fingerprint"
        )

    match_type = provided[0]
    if match_type == "phash":
        return await find_phash_duplicates(
            db,
            parse_phash_hex(phash or ""),
            exclude_video_id=exclude_video_id,
            threshold=threshold,
            public_only=public_only,
        )
    if match_type == "file_sha256":
        return await find_file_sha256_matches(
            db,
            file_sha256 or "",
            exclude_video_id=exclude_video_id,
            public_only=public_only,
        )
    return await find_audio_fingerprint_matches(
        db,
        audio_fingerprint or "",
        exclude_video_id=exclude_video_id,
        public_only=public_only,
    )


async def find_all_hash_duplicates_for_fingerprint(
    db: AsyncSession,
    fp: MediaFingerprint,
    *,
    exclude_video_id: UUID | None = None,
    threshold: int | None = None,
    public_only: bool = True,
) -> list[dict]:
    """Match a fingerprint job against catalog hashes (phash, sha256, chromaprint)."""
    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _extend(rows: list[dict]) -> None:
        for row in rows:
            key = (row["video_sbid"], row["match_type"])
            if key in seen:
                continue
            seen.add(key)
            matches.append(row)

    if fp.file_sha256:
        _extend(
            await find_file_sha256_matches(
                db,
                fp.file_sha256,
                exclude_video_id=exclude_video_id,
                public_only=public_only,
            )
        )
    if fp.audio_fingerprint:
        _extend(
            await find_audio_fingerprint_matches(
                db,
                fp.audio_fingerprint,
                exclude_video_id=exclude_video_id,
                public_only=public_only,
            )
        )
    if fp.phash is not None:
        _extend(
            await find_phash_duplicates(
                db,
                fp.phash,
                exclude_video_id=exclude_video_id,
                threshold=threshold,
                public_only=public_only,
            )
        )

    def _sort_key(row: dict) -> tuple:
        type_rank = {"file_sha256": 0, "audio_fingerprint": 1, "phash": 2}.get(
            row["match_type"], 9
        )
        distance = row["hamming_distance"] if row["hamming_distance"] is not None else -1
        return (type_rank, distance, row["youtube_id"])

    matches.sort(key=_sort_key)
    return matches
