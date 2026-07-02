"""Brand logo gallery API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional, require_submitter, require_write_access
from app.database import get_db
from app.models import Advertiser, AdvertiserStatus, EditType, LogoPopularityChoice, User
from app.schemas import (
    AdvertiserLogoMetadataUpdate,
    AdvertiserLogoPopularityVoteCreate,
    AdvertiserLogoPublic,
    EditPublic,
)
from app.services import EditService
from app.services.advertiser_logos import (
    cast_logo_popularity_vote,
    get_logo_for_advertiser,
    list_advertiser_logos,
)
from app.services.edit_response import build_edit_public
from app.services.logo_metadata import logo_to_state, metadata_snapshot_changed

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
    user: User = Depends(require_write_access),
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


@router.post(
    "/advertisers/{sbid}/logos/{logo_id}/submit-metadata",
    response_model=EditPublic,
    status_code=status.HTTP_201_CREATED,
)
async def submit_advertiser_logo_metadata(
    sbid: UUID,
    logo_id: UUID,
    body: AdvertiserLogoMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    logo = await get_logo_for_advertiser(db, sbid, logo_id)
    if not logo or logo.advertiser.status != AdvertiserStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Logo not found")

    before_state = logo_to_state(logo)
    payload = body.model_dump()
    for key, value in list(payload.items()):
        if isinstance(value, str) and not value.strip():
            payload[key] = None
    after_state = {**before_state, **payload, "logo_id": str(logo.id), "advertiser_id": str(sbid)}
    if not metadata_snapshot_changed(before_state, after_state):
        raise HTTPException(status_code=400, detail="No metadata changes to submit")

    context = logo.label or "Logo version"
    try:
        edit = await EditService.create_edit(
            db,
            user,
            EditType.EDIT_ADVERTISER_LOGO,
            "advertiser_logo",
            after_state,
            before_state=before_state,
            entity_id=logo.id,
            comment=f'Proposed metadata update for "{context}".',
            force_votable=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    await db.refresh(edit, ["votes"])
    return await build_edit_public(db, edit, editor_username=user.username)
