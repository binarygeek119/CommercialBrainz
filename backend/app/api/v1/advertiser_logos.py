"""Brand logo gallery API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_current_user_optional
from app.database import get_db
from app.models import Advertiser, AdvertiserStatus, LogoPopularityChoice, User
from app.schemas import AdvertiserLogoPopularityVoteCreate, AdvertiserLogoPublic
from app.services.advertiser_logos import (
    cast_logo_popularity_vote,
    get_logo_for_advertiser,
    list_advertiser_logos,
)

router = APIRouter(tags=["advertiser-logos"])


@router.get("/advertisers/{sbid}/logos", response_model=list[AdvertiserLogoPublic])
async def get_advertiser_logos(
    sbid: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    result = await db.execute(
        select(Advertiser).where(
            Advertiser.sbid == sbid,
            Advertiser.status == AdvertiserStatus.APPROVED,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Approved brand not found")

    items = await list_advertiser_logos(db, sbid, viewer=user)
    return [AdvertiserLogoPublic(**item) for item in items]


@router.post(
    "/advertisers/{sbid}/logos/{logo_id}/popularity-vote",
    response_model=AdvertiserLogoPublic,
)
async def vote_advertiser_logo_popularity(
    sbid: UUID,
    logo_id: UUID,
    body: AdvertiserLogoPopularityVoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logo = await get_logo_for_advertiser(db, sbid, logo_id)
    if not logo or logo.advertiser.status != AdvertiserStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Logo not found")

    choice = (
        LogoPopularityChoice(body.choice) if body.choice is not None else None
    )
    await cast_logo_popularity_vote(db, logo, user, choice)
    items = await list_advertiser_logos(db, sbid, viewer=user)
    match = next((item for item in items if item["id"] == logo_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Logo not found")
    return AdvertiserLogoPublic(**match)
