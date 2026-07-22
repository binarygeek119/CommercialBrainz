"""Serialize Video ORM rows for public API responses."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Commercial, User, Video, VideoVisibility
from app.schemas import VideoPublic
from app.services.fingerprint_queries import format_phash_hex
from app.services.video_popularity import enrich_video_public, list_commercial_video_meta
from app.utils import youtube_thumbnail_url


def commercial_list_thumbnail_url(commercial: Commercial) -> str | None:
    """Best public-video thumbnail for commercials list cards (main video preferred)."""
    public = [v for v in commercial.videos if v.visibility == VideoVisibility.PUBLIC]
    public.sort(
        key=lambda v: (
            0 if commercial.main_video_id and v.sbid == commercial.main_video_id else 1,
            -v.popularity_score,
            v.created_at,
        )
    )
    for v in public:
        thumb = video_to_public_dict(v).get("thumbnail_url")
        if thumb:
            return thumb
    return None


def video_to_public_dict(v: Video) -> dict:
    thumb = v.thumbnail_url
    if not thumb and v.youtube_id and v.visibility == VideoVisibility.PUBLIC:
        thumb = youtube_thumbnail_url(v.youtube_id)
    return {
        "sbid": v.sbid,
        "commercial_id": v.commercial_id,
        "youtube_id": v.youtube_id if v.visibility == VideoVisibility.PUBLIC else None,
        "youtube_url": v.youtube_url if v.visibility == VideoVisibility.PUBLIC else None,
        "thumbnail_url": thumb if v.visibility == VideoVisibility.PUBLIC else None,
        "channel_name": v.channel_name,
        "upload_date": v.upload_date.isoformat() if v.upload_date else None,
        "duration_ms": v.duration_ms,
        "aspect_ratio": v.aspect_ratio,
        "resolution": v.resolution,
        "language": v.language,
        "region": v.region,
        "sub_region": v.sub_region,
        "market": v.market,
        "first_aired_date": v.first_aired_date.isoformat() if v.first_aired_date else None,
        "last_aired_date": v.last_aired_date.isoformat() if v.last_aired_date else None,
        "network": v.network,
        "transcript": v.transcript,
        "slogan": v.slogan,
        "cta_text": v.cta_text,
        "metadata": v.extra_data,
        "visibility": v.visibility.value,
        "phash": format_phash_hex(v.phash),
        "file_sha256": v.file_sha256,
        "audio_fingerprint": v.audio_fingerprint,
        "hash_status": v.hash_status.value if v.hash_status else None,
        "hashed_at": v.hashed_at,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


def video_to_public(v: Video) -> VideoPublic:
    return VideoPublic(**video_to_public_dict(v))


async def list_commercial_videos_public(
    db: AsyncSession,
    commercial: Commercial,
    *,
    viewer: User | None = None,
) -> list[VideoPublic]:
    public_videos = [v for v in commercial.videos if v.visibility == VideoVisibility.PUBLIC]
    public_videos.sort(key=lambda v: (-v.popularity_score, v.created_at))
    main_id, viewer_votes = await list_commercial_video_meta(db, commercial.sbid, viewer=viewer)
    return [
        VideoPublic(
            **enrich_video_public(
                video_to_public_dict(v),
                main_video_id=main_id,
                viewer_votes=viewer_votes,
                video=v,
            )
        )
        for v in public_videos
    ]
