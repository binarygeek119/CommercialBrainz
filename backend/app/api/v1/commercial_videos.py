"""Commercial video links — popularity voting and split proposals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user_optional, require_submitter, require_write_access
from app.config import get_settings
from app.database import get_db
from app.models import Commercial, EditType, LogoPopularityChoice, User, VideoVisibility
from app.schemas import (
    AdvertiserLogoPopularityVoteCreate,
    CommercialSplitSubmit,
    EditPublic,
    VideoPublic,
)
from app.services import EditService
from app.services.commercial_split import (
    count_public_videos,
    has_open_split_edit,
    split_after_state,
    split_before_state,
)
from app.services.edit_response import build_edit_public
from app.services.submission_terms import validate_and_record_terms_acceptance
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

    choice = LogoPopularityChoice(
    body.choice) if body.choice is not None else None
    await cast_video_popularity_vote(db, video, user, choice)
    await db.commit()
    await db.refresh(commercial, attribute_names=["videos"])

    items = await list_commercial_videos_public(db, commercial, viewer=user)
    match = next((item for item in items if item.sbid == video_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Video link not found")
    return match


@router.post(
    "/commercials/{sbid}/videos/{video_id}/submit-split",
    response_model=EditPublic,
    status_code=201,
)
async def submit_commercial_split(
    sbid: UUID,
    video_id: UUID,
    body: CommercialSplitSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    try:
        await validate_and_record_terms_acceptance(db, user, body.terms_agreed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(Commercial)
        .options(selectinload(Commercial.products))
        .where(Commercial.sbid == sbid)
    )
    commercial = result.scalar_one_or_none()
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")

    video = await get_video_for_commercial(db, sbid, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video link not found")
    if video.visibility != VideoVisibility.PUBLIC:
        raise HTTPException(status_code=400,
     detail="Only public links can be split off")

    if await count_public_videos(db, commercial.sbid) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot split the only link on a commercial — add another "
                "link first or remove this one instead."
            ),
        )

    if await has_open_split_edit(db, video.sbid):
        raise HTTPException(
            status_code=409,
            detail="An open split proposal already exists for this link.",
        )

    payload = body.model_dump(exclude={"comment", "terms_agreed"})
    if "products" in payload:
        payload["products"] = [str(p).strip()
                                   for p in payload["products"] if str(p).strip()]
    before_state = split_before_state(commercial, video)
    after_state = split_after_state(commercial, video, payload)

    video_label = video.version_label or video.slogan or video.youtube_id or "link"
    comment = body.comment.strip() if body.comment and body.comment.strip() else None
    default_comment = (
    f'Propose splitting "{video_label}" from "{
        commercial.title}" into its own commercial ' f'"{
            payload["title"].strip()}".' )

    try:
        edit = await EditService.create_edit(
            db,
            user,
            EditType.SPLIT_COMMERCIAL,
            "commercial",
            after_state,
            before_state=before_state,
            entity_id=commercial.sbid,
            comment=comment or default_comment,
            force_votable=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    edit.expires_at = datetime.now(
        UTC) + timedelta(days=get_settings().split_open_days)

    await db.refresh(edit, ["votes"])
    return await build_edit_public(db, edit, editor_username=user.username)
