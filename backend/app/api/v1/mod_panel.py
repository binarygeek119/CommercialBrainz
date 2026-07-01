from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_mod
from app.database import get_db
from app.models import DMCATakedown, DMCAStatus, Edit, EditStatus, FingerprintStatus, MediaFingerprint, User
from app.schemas import EditPublic, ModStats
from app.services import EditService
from app.services.edit_response import build_edit_public

router = APIRouter(prefix="/mod", tags=["mod"])


@router.get("/stats", response_model=ModStats)
async def mod_stats(
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    open_edits = await db.scalar(
        select(func.count()).select_from(Edit).where(Edit.status == EditStatus.OPEN)
    )
    dmca_submitted = await db.scalar(
        select(func.count())
        .select_from(DMCATakedown)
        .where(DMCATakedown.status == DMCAStatus.SUBMITTED)
    )
    dmca_review = await db.scalar(
        select(func.count())
        .select_from(DMCATakedown)
        .where(DMCATakedown.status == DMCAStatus.UNDER_REVIEW)
    )
    dmca_hidden = await db.scalar(
        select(func.count())
        .select_from(DMCATakedown)
        .where(DMCATakedown.status == DMCAStatus.LINK_HIDDEN)
    )
    pending_fp = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.PENDING)
    )
    failed_fp = await db.scalar(
        select(func.count())
        .select_from(MediaFingerprint)
        .where(MediaFingerprint.status == FingerprintStatus.FAILED)
    )
    return ModStats(
        open_edits=open_edits or 0,
        dmca_submitted=dmca_submitted or 0,
        dmca_under_review=dmca_review or 0,
        dmca_link_hidden=dmca_hidden or 0,
        pending_fingerprints=pending_fp or 0,
        failed_fingerprints=failed_fp or 0,
    )


@router.post("/edits/{edit_id}/apply", response_model=EditPublic)
async def mod_apply_edit(
    edit_id: UUID,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    result = await db.execute(
        select(Edit).options(selectinload(Edit.votes)).where(Edit.id == edit_id)
    )
    edit = result.scalar_one_or_none()
    if not edit or edit.status != EditStatus.OPEN:
        raise HTTPException(status_code=404, detail="Open edit not found")

    edit.status = EditStatus.APPLIED
    edit.closed_at = datetime.now(UTC)
    pending_hash = await EditService._complete_applied_edit(db, edit)

    await db.flush()

    if pending_hash is not None:
        from app.services.hash_queue import enqueue_hash_job

        await enqueue_hash_job(pending_hash)

    return await build_edit_public(db, edit)


@router.post("/edits/{edit_id}/reject", response_model=EditPublic)
async def mod_reject_edit(
    edit_id: UUID,
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    result = await db.execute(
        select(Edit).options(selectinload(Edit.votes)).where(Edit.id == edit_id)
    )
    edit = result.scalar_one_or_none()
    if not edit or edit.status != EditStatus.OPEN:
        raise HTTPException(status_code=404, detail="Open edit not found")

    await EditService.reject_edit(db, edit)
    await db.flush()
    return await build_edit_public(db, edit)
