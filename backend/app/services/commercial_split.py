"""Helpers for splitting a video link into its own commercial."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Commercial, Edit, EditStatus, EditType, Video, VideoVisibility
from app.services.commercial_metadata import commercial_to_state


async def count_public_videos(db: AsyncSession, commercial_id: UUID) -> int:
    result = await db.scalar(
        select(func.count())
        .select_from(Video)
        .where(Video.commercial_id == commercial_id, Video.visibility == VideoVisibility.PUBLIC)
    )
    return int(result or 0)


async def has_open_split_edit(db: AsyncSession, video_id: UUID) -> bool:
    result = await db.execute(
        select(Edit.id).where(
            Edit.edit_type == EditType.SPLIT_COMMERCIAL,
            Edit.status == EditStatus.OPEN,
            Edit.after_state["video_id"].astext == str(video_id),
        )
    )
    return result.scalar_one_or_none() is not None


def video_snapshot(video: Video) -> dict:
    return {
        k: v
        for k, v in {
            "video_id": str(video.sbid),
            "youtube_id": video.youtube_id,
            "youtube_url": video.youtube_url,
            "version_label": video.version_label,
            "slogan": video.slogan,
            "language": video.language,
            "region": video.region,
            "sub_region": video.sub_region,
        }.items()
        if v not in (None, "")
    }


def split_before_state(commercial: Commercial, video: Video) -> dict:
    return {
        "source_commercial_id": str(commercial.sbid),
        "video_id": str(video.sbid),
        "source_commercial": commercial_to_state(commercial),
        "video": video_snapshot(video),
    }


def split_after_state(
    commercial: Commercial,
    video: Video,
    payload: dict,
) -> dict:
    products = [str(p).strip() for p in payload.get("products", []) if str(p).strip()]
    commercial_data = {
        "title": payload["title"].strip(),
        "year": payload.get("year"),
        "decade": payload.get("decade"),
        "campaign_name": payload.get("campaign_name"),
        "description": payload.get("description"),
        "products": products,
    }
    if commercial.advertiser_id:
        commercial_data["advertiser_id"] = str(commercial.advertiser_id)
    if commercial.agency_id:
        commercial_data["agency_id"] = str(commercial.agency_id)
    return {
        "source_commercial_id": str(commercial.sbid),
        "video_id": str(video.sbid),
        "commercial": {k: v for k, v in commercial_data.items() if v not in (None, "", [])},
    }


def suggested_split_title(commercial: Commercial, video: Video) -> str:
    label = (video.version_label or video.slogan or "").strip()
    if label:
        return f"{commercial.title} ({label})"
    return commercial.title
