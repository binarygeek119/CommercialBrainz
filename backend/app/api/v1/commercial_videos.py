"""Commercial video links — popularity voting."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional, require_write_access
from app.database import get_db
from app.models import Commercial, LogoPopularityChoice, User
from app.schemas import AdvertiserLogoPopularityVoteCreate, VideoPublic
from app.services.video_popularity import cast_video_popularity_vote, get_video_for_commercial
from app.services.video_response import list_commercial_videos_public

router = APIRouter(tags=["commercial-videos"])


@router.get("/commercials/{sbid}/videos", response_model=list[VideoPublic])
async def get_commercial_videos(
    sbid: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    result = await db.execute(select(Commercial).where(Commercial.sbid == sbid))
    commercial = result.scalar_one_or_none()
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    return await list_commercial_videos_public(db, commercial, viewer=user)


@router.post(
    "/commercials/{sbid}/videos/{video_id}/popularity-vote",
    response_model=VideoPublic,
)
async def vote_commercial_video_popularity(
    sbid: UUID,
    video_id: UUID,
    body: AdvertiserLogoPopularityVoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    result = await db.execute(select(Commercial).where(Commercial.sbid == sbid))
    commercial = result.scalar_one_or_none()
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")

    video = await get_video_for_commercial(db, sbid, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video link not found")

    choice = LogoPopularityChoice(body.choice) if body.choice is not None else None
    await cast_video_popularity_vote(db, video, user, choice)
    await db.commit()
    await db.refresh(commercial, attribute_names=["videos"])

    items = await list_commercial_videos_public(db, commercial, viewer=user)
    match = next((item for item in items if item.sbid == video_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Video link not found")
    return match
