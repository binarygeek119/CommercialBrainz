from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user, require_mod
from app.auth.security import user_can_vote
from app.database import get_db
from app.models import Edit, EditStatus, EditType, User, Vote, VoteChoice
from app.schemas import EditCreate, EditPublic, PaginatedResponse, VideoCreate, VoteCreate, VotePublic
from app.services import EditService
from app.utils import extract_youtube_id

router = APIRouter(prefix="/edits", tags=["edits"])


@router.post("", response_model=EditPublic, status_code=status.HTTP_201_CREATED)
async def create_edit(
    data: EditCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        edit_type = EditType(data.edit_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid edit type") from e

    edit = await EditService.create_edit(
        db,
        user,
        edit_type,
        data.entity_type,
        data.after_state,
        before_state=data.before_state,
        entity_id=data.entity_id,
        comment=data.comment,
        force_votable=data.force_votable,
    )
    await db.refresh(edit, ["votes"])
    return EditPublic(
        id=edit.id,
        edit_type=edit.edit_type.value,
        status=edit.status.value,
        entity_type=edit.entity_type,
        entity_id=edit.entity_id,
        before_state=edit.before_state,
        after_state=edit.after_state,
        editor_id=edit.editor_id,
        comment=edit.comment,
        expires_at=edit.expires_at,
        closed_at=edit.closed_at,
        created_at=edit.created_at,
        votes=[],
    )


@router.post("/submit-video", response_model=EditPublic, status_code=status.HTTP_201_CREATED)
async def submit_video(
    data: VideoCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        youtube_id = data.youtube_id or extract_youtube_id(data.youtube_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    after_state = data.model_dump(exclude={"comment", "force_votable", "commercial"})
    after_state["youtube_id"] = youtube_id
    after_state["youtube_url"] = data.youtube_url

    if data.commercial:
        after_state["commercial"] = data.commercial.model_dump()
        if data.commercial.products:
            after_state["commercial"]["products"] = data.commercial.products
        if data.commercial.advertiser_id:
            after_state["commercial"]["advertiser_id"] = str(data.commercial.advertiser_id)
        if data.commercial.agency_id:
            after_state["commercial"]["agency_id"] = str(data.commercial.agency_id)

    if data.commercial_id:
        after_state["commercial_id"] = str(data.commercial_id)

    edit = await EditService.create_edit(
        db,
        user,
        EditType.CREATE_VIDEO,
        "video",
        after_state,
        comment=data.comment,
        force_votable=data.force_votable,
    )
    return EditPublic(
        id=edit.id,
        edit_type=edit.edit_type.value,
        status=edit.status.value,
        entity_type=edit.entity_type,
        entity_id=edit.entity_id,
        before_state=edit.before_state,
        after_state=edit.after_state,
        editor_id=edit.editor_id,
        comment=edit.comment,
        expires_at=edit.expires_at,
        closed_at=edit.closed_at,
        created_at=edit.created_at,
        votes=[],
    )


@router.get("/open", response_model=PaginatedResponse)
async def list_open_edits(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    stmt = (
        select(Edit)
        .options(selectinload(Edit.votes))
        .where(Edit.status == EditStatus.OPEN)
        .order_by(Edit.created_at.desc())
    )
    result = await db.execute(stmt.offset(offset).limit(limit))
    edits = result.scalars().all()
    items = []
    for edit in edits:
        items.append(
            EditPublic(
                id=edit.id,
                edit_type=edit.edit_type.value,
                status=edit.status.value,
                entity_type=edit.entity_type,
                entity_id=edit.entity_id,
                before_state=edit.before_state,
                after_state=edit.after_state,
                editor_id=edit.editor_id,
                comment=edit.comment,
                expires_at=edit.expires_at,
                closed_at=edit.closed_at,
                created_at=edit.created_at,
                votes=[
                    VotePublic(
                        id=v.id,
                        voter_id=v.voter_id,
                        choice=v.choice.value,
                        comment=v.comment,
                        created_at=v.created_at,
                    )
                    for v in edit.votes
                ],
            ).model_dump()
        )
    return PaginatedResponse(items=items, total=len(items), offset=offset, limit=limit)


@router.get("/{edit_id}", response_model=EditPublic)
async def get_edit(edit_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Edit).options(selectinload(Edit.votes)).where(Edit.id == edit_id)
    )
    edit = result.scalar_one_or_none()
    if not edit:
        raise HTTPException(status_code=404, detail="Edit not found")
    return EditPublic(
        id=edit.id,
        edit_type=edit.edit_type.value,
        status=edit.status.value,
        entity_type=edit.entity_type,
        entity_id=edit.entity_id,
        before_state=edit.before_state,
        after_state=edit.after_state,
        editor_id=edit.editor_id,
        comment=edit.comment,
        expires_at=edit.expires_at,
        closed_at=edit.closed_at,
        created_at=edit.created_at,
        votes=[
            VotePublic(
                id=v.id,
                voter_id=v.voter_id,
                choice=v.choice.value,
                comment=v.comment,
                created_at=v.created_at,
            )
            for v in edit.votes
        ],
    )


@router.post("/{edit_id}/vote", response_model=VotePublic)
async def vote_on_edit(
    edit_id: UUID,
    data: VoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user_can_vote(user):
        raise HTTPException(status_code=403, detail="Not eligible to vote yet")

    result = await db.execute(select(Edit).where(Edit.id == edit_id))
    edit = result.scalar_one_or_none()
    if not edit or edit.status != EditStatus.OPEN:
        raise HTTPException(status_code=404, detail="Open edit not found")

    try:
        choice = VoteChoice(data.choice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid vote choice") from e

    try:
        vote = await EditService.cast_vote(db, edit, user, choice, data.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return VotePublic(
        id=vote.id,
        voter_id=vote.voter_id,
        choice=vote.choice.value,
        comment=vote.comment,
        created_at=vote.created_at,
    )


@router.post("/{edit_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_edit(
    edit_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Edit).where(Edit.id == edit_id))
    edit = result.scalar_one_or_none()
    if not edit or edit.status != EditStatus.OPEN:
        raise HTTPException(status_code=404, detail="Open edit not found")
    if edit.editor_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Cannot cancel this edit")
    edit.status = EditStatus.CANCELLED
    from datetime import UTC, datetime

    edit.closed_at = datetime.now(UTC)
