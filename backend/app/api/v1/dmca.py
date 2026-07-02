from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin, require_mod, require_write_access
from app.database import get_db
from app.models import DMCATakedown, DMCAStatus, User, Video
from app.schemas import DMCACounterSubmit, DMCAPublic, DMCAReview, DMCASubmit, PaginatedResponse
from app.services import DMCAService
from app.services.email import notify_dmca_decision, notify_dmca_submitted

router = APIRouter(prefix="/dmca", tags=["dmca"])


@router.post("", response_model=DMCAPublic, status_code=status.HTTP_201_CREATED)
async def submit_dmca(data: DMCASubmit, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.sbid == data.video_sbid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Video not found")

    takedown = await DMCAService.submit(
        db,
        {
            "video_id": data.video_sbid,
            "claimant_name": data.claimant_name,
            "claimant_email": data.claimant_email,
            "claimant_address": data.claimant_address,
            "claim_text": data.claim_text,
            "signature": data.signature,
        },
    )
    await notify_dmca_submitted(data.claimant_email, str(data.video_sbid))
    return DMCAPublic(
        id=takedown.id,
        video_id=takedown.video_id,
        status=takedown.status.value,
        claimant_name=takedown.claimant_name,
        claimant_email=takedown.claimant_email,
        claim_text=takedown.claim_text,
        review_notes=takedown.review_notes,
        created_at=takedown.created_at,
        updated_at=takedown.updated_at,
    )


@router.get("/queue", response_model=PaginatedResponse)
async def dmca_queue(
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    stmt = select(DMCATakedown).order_by(DMCATakedown.created_at.desc())
    if status_filter:
        try:
            stmt = stmt.where(DMCATakedown.status == DMCAStatus(status_filter))
        except ValueError:
            pass
    result = await db.execute(stmt.offset(offset).limit(limit))
    items = []
    for t in result.scalars().all():
        items.append(
            DMCAPublic(
                id=t.id,
                video_id=t.video_id,
                status=t.status.value,
                claimant_name=t.claimant_name,
                claimant_email=t.claimant_email,
                claim_text=t.claim_text,
                review_notes=t.review_notes,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ).model_dump()
        )
    return PaginatedResponse(items=items, total=len(items), offset=offset, limit=limit)


@router.post("/{takedown_id}/review", response_model=DMCAPublic)
async def review_dmca(
    takedown_id: UUID,
    data: DMCAReview,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    result = await db.execute(select(DMCATakedown).where(DMCATakedown.id == takedown_id))
    takedown = result.scalar_one_or_none()
    if not takedown:
        raise HTTPException(status_code=404, detail="DMCA request not found")

    try:
        new_status = DMCAStatus(data.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid status") from e

    if new_status not in (
        DMCAStatus.UNDER_REVIEW,
        DMCAStatus.LINK_HIDDEN,
        DMCAStatus.REJECTED,
        DMCAStatus.RESTORED,
        DMCAStatus.PERMANENTLY_REMOVED,
    ):
        raise HTTPException(status_code=400, detail="Invalid review status")

    takedown = await DMCAService.review(db, takedown, mod, new_status, data.review_notes)
    await notify_dmca_decision(takedown.claimant_email, str(takedown.video_id), new_status.value)
    return DMCAPublic(
        id=takedown.id,
        video_id=takedown.video_id,
        status=takedown.status.value,
        claimant_name=takedown.claimant_name,
        claimant_email=takedown.claimant_email,
        claim_text=takedown.claim_text,
        review_notes=takedown.review_notes,
        created_at=takedown.created_at,
        updated_at=takedown.updated_at,
    )


@router.post("/{takedown_id}/counter", response_model=DMCAPublic)
async def counter_dmca(
    takedown_id: UUID,
    data: DMCACounterSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    result = await db.execute(select(DMCATakedown).where(DMCATakedown.id == takedown_id))
    takedown = result.scalar_one_or_none()
    if not takedown:
        raise HTTPException(status_code=404, detail="DMCA request not found")
    if takedown.status != DMCAStatus.LINK_HIDDEN:
        raise HTTPException(status_code=400, detail="Counter-notification not applicable")

    takedown.counter_claim_text = data.counter_claim_text
    takedown.counter_claimant_id = user.id
    takedown.status = DMCAStatus.UNDER_REVIEW
    await db.flush()

    return DMCAPublic(
        id=takedown.id,
        video_id=takedown.video_id,
        status=takedown.status.value,
        claimant_name=takedown.claimant_name,
        claimant_email=takedown.claimant_email,
        claim_text=takedown.claim_text,
        review_notes=takedown.review_notes,
        created_at=takedown.created_at,
        updated_at=takedown.updated_at,
    )
