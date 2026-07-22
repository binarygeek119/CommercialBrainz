from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_mod
from app.database import get_db
from app.models import (
    AccountDeletionRequest,
    AccountDeletionStatus,
    DMCAStatus,
    DMCATakedown,
    Edit,
    EditStatus,
    FingerprintStatus,
    MediaFingerprint,
    User,
)
from app.schemas import (
    AccountDeletionRequestPublic,
    AccountDeletionReview,
    DeadLinkPublic,
    EditPublic,
    FingerprintQueueStatus,
    LinkCheckRunResult,
    ModStats,
)
from app.services import EditService
from app.services.account_settings import (
    approve_deletion_request,
    list_pending_deletion_requests,
    reject_deletion_request,
)
from app.services.edit_response import build_edit_public
from app.services.fingerprint_queue_status import get_fingerprint_queue_status
from app.services.link_check import (
    check_video_link,
    count_flagged_dead_links,
    dismiss_dead_link,
    enqueue_link_check,
    flagged_video_to_dict,
    get_video_for_link_check,
    list_flagged_dead_links,
)

router = APIRouter(prefix="/mod", tags=["mod"])


def _deletion_request_public(record: AccountDeletionRequest) -> AccountDeletionRequestPublic:
    return AccountDeletionRequestPublic(
        id=record.id,
        status=record.status.value,
        points_to_transfer=float(record.points_to_transfer or 0),
        recipient_username=record.recipient.username if record.recipient else None,
        review_notes=record.review_notes,
        reviewed_at=record.reviewed_at,
        created_at=record.created_at,
        username=record.user.username if record.user else None,
    )


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
    pending_deletions = await db.scalar(
        select(func.count())
        .select_from(AccountDeletionRequest)
        .where(AccountDeletionRequest.status == AccountDeletionStatus.PENDING)
    )
    dead_links = await count_flagged_dead_links(db)
    return ModStats(
        open_edits=open_edits or 0,
        dmca_submitted=dmca_submitted or 0,
        dmca_under_review=dmca_review or 0,
        dmca_link_hidden=dmca_hidden or 0,
        pending_fingerprints=pending_fp or 0,
        failed_fingerprints=failed_fp or 0,
        pending_deletion_requests=pending_deletions or 0,
        dead_links=dead_links,
    )


@router.get("/fingerprint-queue", response_model=FingerprintQueueStatus)
async def mod_fingerprint_queue(
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    return FingerprintQueueStatus(**await get_fingerprint_queue_status(db))


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


@router.get("/deletion-requests", response_model=list[AccountDeletionRequestPublic])
async def mod_list_deletion_requests(
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    records = await list_pending_deletion_requests(db)
    return [_deletion_request_public(record) for record in records]


@router.post("/deletion-requests/{request_id}/approve", response_model=AccountDeletionRequestPublic)
async def mod_approve_deletion_request(
    request_id: UUID,
    body: AccountDeletionReview,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    try:
        record = await approve_deletion_request(db, request_id, mod, body.review_notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record, attribute_names=["user", "recipient"])
    return _deletion_request_public(record)


@router.post("/deletion-requests/{request_id}/reject", response_model=AccountDeletionRequestPublic)
async def mod_reject_deletion_request(
    request_id: UUID,
    body: AccountDeletionReview,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    try:
        record = await reject_deletion_request(db, request_id, mod, body.review_notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record, attribute_names=["user", "recipient"])
    return _deletion_request_public(record)


@router.get("/dead-links", response_model=list[DeadLinkPublic])
async def mod_list_dead_links(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    videos = await list_flagged_dead_links(db, offset=offset, limit=limit)
    return [DeadLinkPublic(**flagged_video_to_dict(v)) for v in videos]


@router.post("/dead-links/check", response_model=LinkCheckRunResult)
async def mod_trigger_dead_link_check(
    limit: int | None = None,
    _mod: User = Depends(require_mod),
):
    """Enqueue a full (or limited) public YouTube link scan on the worker."""
    try:
        await enqueue_link_check(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return LinkCheckRunResult(
        queued=True,
        message="YouTube link check queued on the background worker",
    )


@router.post("/dead-links/{video_id}/dismiss", response_model=DeadLinkPublic)
async def mod_dismiss_dead_link(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    video = await dismiss_dead_link(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    await db.commit()
    video = await get_video_for_link_check(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return DeadLinkPublic(**flagged_video_to_dict(video))


@router.post("/dead-links/{video_id}/recheck", response_model=DeadLinkPublic)
async def mod_recheck_dead_link(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    video = await get_video_for_link_check(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    await check_video_link(db, video)
    await db.commit()
    video = await get_video_for_link_check(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return DeadLinkPublic(**flagged_video_to_dict(video))
