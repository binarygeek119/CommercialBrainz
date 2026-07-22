"""Power-user bulk playlist submit (hidden from non–power users)."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_bulk_submit_granted, require_bulk_submitter
from app.database import get_db
from app.models import User
from app.schemas import (
    BulkItemSubmitRequest,
    BulkPlaylistCheckCounts,
    BulkPlaylistCheckEntry,
    BulkPlaylistCheckPublic,
    BulkPlaylistImportRequest,
    BulkSubmissionBatchPublic,
    BulkSubmissionItemPublic,
    EditPublic,
    PowerUserTermsAccept,
    PowerUserTermsPublic,
)
from app.services.bulk_submit import (
    batch_counts,
    batch_to_dict,
    cancel_bulk_batch,
    create_bulk_batch,
    enqueue_bulk_playlist_import,
    finalize_bulk_item,
    get_owner_item,
    item_to_dict,
    list_owner_batches,
    list_owner_items,
    preview_playlist_duplicates,
    rehash_item,
    skip_item,
)
from app.services.edit_response import build_edit_public
from app.services.hash_queue import enqueue_hash_job
from app.services.power_user_terms import (
    get_active_power_user_terms,
    power_user_terms_to_dict,
    validate_and_record_power_user_terms,
)

router = APIRouter(prefix="/bulk-submit", tags=["bulk-submit"])


@router.get("/terms", response_model=PowerUserTermsPublic)
async def get_power_user_terms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submit_granted),
):
    doc = await get_active_power_user_terms(db)
    if not doc:
        raise HTTPException(status_code=404, detail="Forbidden")
    payload = power_user_terms_to_dict(doc)
    payload["accepted"] = user.power_user_terms_version == doc.version
    return PowerUserTermsPublic(**payload)


@router.post("/terms/accept", response_model=PowerUserTermsPublic)
async def accept_power_user_terms(
    body: PowerUserTermsAccept,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submit_granted),
):
    try:
        doc = await validate_and_record_power_user_terms(db, user, body.agreed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    payload = power_user_terms_to_dict(doc)
    payload["accepted"] = True
    return PowerUserTermsPublic(**payload)


@router.post("/playlists/check", response_model=BulkPlaylistCheckPublic)
async def check_playlist_duplicates(
    body: BulkPlaylistImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    """Expand a playlist and report duplicate links before starting an import."""
    try:
        result = await preview_playlist_duplicates(db, user, body.playlist_url)
    except Exception as exc:  # noqa: BLE001 — yt-dlp / parse errors become 400
        raise HTTPException(status_code=400, detail=str(exc)[:500]) from exc
    return BulkPlaylistCheckPublic(
        playlist_id=result.get("playlist_id"),
        playlist_title=result.get("playlist_title"),
        playlist_url=result["playlist_url"],
        counts=BulkPlaylistCheckCounts(**result["counts"]),
        entries=[BulkPlaylistCheckEntry(**entry) for entry in result["entries"]],
        staging_window=int(result.get("staging_window") or 10),
    )


@router.post("/playlists", response_model=BulkSubmissionBatchPublic, status_code=201)
async def start_playlist_import(
    body: BulkPlaylistImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    batch = await create_bulk_batch(
        db,
        user,
        body.playlist_url,
        defaults=(
            body.defaults.model_dump(exclude_none=True) if body.defaults is not None else None
        ),
    )
    await db.commit()
    background_tasks.add_task(enqueue_bulk_playlist_import, batch.id)
    return BulkSubmissionBatchPublic(**batch_to_dict(batch))


@router.get("/batches", response_model=list[BulkSubmissionBatchPublic])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    batches = await list_owner_batches(db, user.id)
    out: list[BulkSubmissionBatchPublic] = []
    for batch in batches:
        counts = await batch_counts(db, batch.id)
        out.append(BulkSubmissionBatchPublic(**batch_to_dict(batch, **counts)))
    return out


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    """Cancel a bulk playlist import and remove its queue/staging items."""
    batch = await cancel_bulk_batch(db, user.id, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    await db.commit()


@router.get("/items", response_model=list[BulkSubmissionItemPublic])
async def list_items(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    items = await list_owner_items(db, user.id, status=status, offset=offset, limit=limit)
    await db.commit()
    return [BulkSubmissionItemPublic(**item_to_dict(i)) for i in items]


@router.get("/items/{item_id}", response_model=BulkSubmissionItemPublic)
async def get_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    item = await get_owner_item(db, user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    await db.commit()
    return BulkSubmissionItemPublic(**item_to_dict(item))


@router.post("/items/{item_id}/submit", response_model=EditPublic)
async def submit_item(
    item_id: UUID,
    body: BulkItemSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    item = await get_owner_item(db, user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        edit, refill_fps = await finalize_bulk_item(db, user, item, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(edit, ["votes"])

    # If a new FINAL fingerprint was created, enqueue it.
    from sqlalchemy import select

    from app.models import FingerprintStatus, MediaFingerprint

    result = await db.execute(
        select(MediaFingerprint.id).where(
            MediaFingerprint.edit_id == edit.id,
            MediaFingerprint.status == FingerprintStatus.PENDING,
        )
    )
    for (fp_id,) in result.all():
        background_tasks.add_task(enqueue_hash_job, fp_id)
    for fp_id in refill_fps:
        background_tasks.add_task(enqueue_hash_job, fp_id)

    return await build_edit_public(db, edit, editor_username=user.username)


@router.post("/items/{item_id}/skip", response_model=BulkSubmissionItemPublic)
async def skip_bulk_item(
    item_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    item = await get_owner_item(db, user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        refill_fps = await skip_item(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    for fp_id in refill_fps:
        background_tasks.add_task(enqueue_hash_job, fp_id)
    return BulkSubmissionItemPublic(**item_to_dict(item))


@router.post("/items/{item_id}/rehash", response_model=BulkSubmissionItemPublic)
async def rehash_bulk_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_bulk_submitter),
):
    item = await get_owner_item(db, user.id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        await rehash_item(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return BulkSubmissionItemPublic(**item_to_dict(item))
