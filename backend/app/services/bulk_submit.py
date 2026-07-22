"""Bulk playlist staging: import, hash, and finalize into normal video edits."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    BulkSubmissionBatch,
    BulkSubmissionBatchStatus,
    BulkSubmissionItem,
    BulkSubmissionItemStatus,
    Edit,
    EditStatus,
    EditType,
    FingerprintPhase,
    FingerprintStatus,
    MediaFingerprint,
    User,
    Video,
)
from app.services.bulk_import_marker import ensure_bulk_imported_tag
from app.services.hash_queue import enqueue_hash_job
from app.services.media_hash import _copy_to_video
from app.services.youtube_metadata import expand_youtube_playlist, fetch_youtube_metadata
from app.utils import youtube_watch_url

logger = logging.getLogger(__name__)
settings = get_settings()


async def enqueue_bulk_playlist_import(batch_id: UUID) -> None:
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("import_bulk_playlist", str(batch_id))
    finally:
        await pool.aclose()


async def create_bulk_batch(
    db: AsyncSession,
    owner: User,
    playlist_url: str,
) -> BulkSubmissionBatch:
    batch = BulkSubmissionBatch(
        owner_id=owner.id,
        playlist_url=playlist_url.strip(),
        status=BulkSubmissionBatchStatus.IMPORTING,
    )
    db.add(batch)
    await db.flush()
    return batch


async def import_bulk_playlist(batch_id: UUID) -> dict[str, Any]:
    """Worker entry: expand playlist, fetch metadata, enqueue preview hashes."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        batch = await db.get(BulkSubmissionBatch, batch_id)
        if not batch:
            return {"ok": False, "error": "batch not found"}

        try:
            expanded = expand_youtube_playlist(
                batch.playlist_url,
                max_items=settings.bulk_submit_max_playlist_items,
            )
        except Exception as exc:  # noqa: BLE001
            batch.status = BulkSubmissionBatchStatus.FAILED
            batch.error_message = str(exc)[:500]
            batch.updated_at = datetime.now(UTC)
            await db.commit()
            return {"ok": False, "error": str(exc)}

        batch.playlist_id = expanded.get("playlist_id")
        batch.playlist_title = expanded.get("playlist_title")
        entries = expanded.get("entries") or []
        batch.item_count = len(entries)
        await db.flush()

        fingerprint_ids: list[UUID] = []
        for entry in entries:
            youtube_id = entry["youtube_id"]
            item = BulkSubmissionItem(
                batch_id=batch.id,
                owner_id=batch.owner_id,
                youtube_id=youtube_id,
                youtube_url=entry.get("youtube_url") or youtube_watch_url(youtube_id),
                position=int(entry.get("position") or 0),
                status=BulkSubmissionItemStatus.PENDING_META,
                extra_data={"title": entry.get("title")},
            )
            db.add(item)
            await db.flush()

            existing = await db.scalar(
                select(Video.sbid).where(Video.youtube_id == youtube_id).limit(1)
            )
            if existing:
                item.status = BulkSubmissionItemStatus.DUPLICATE
                item.error_message = "Already in catalog"
                item.extra_data = {
                    **(item.extra_data or {}),
                    "existing_video_sbid": str(existing),
                }
                continue

            try:
                meta = fetch_youtube_metadata(youtube_id)
                item.extra_data = meta
                item.status = BulkSubmissionItemStatus.HASHING
                fp = MediaFingerprint(
                    edit_id=None,
                    youtube_id=youtube_id,
                    phase=FingerprintPhase.PREVIEW,
                    status=FingerprintStatus.PENDING,
                )
                db.add(fp)
                await db.flush()
                item.fingerprint_id = fp.id
                fingerprint_ids.append(fp.id)
            except Exception as exc:  # noqa: BLE001
                item.status = BulkSubmissionItemStatus.FAILED
                item.error_message = str(exc)[:500]

        batch.status = BulkSubmissionBatchStatus.READY
        batch.updated_at = datetime.now(UTC)
        await db.commit()

    for fp_id in fingerprint_ids:
        await enqueue_hash_job(fp_id)

    # Mark hashing items ready when fingerprint already completed (fast path) via refresh job.
    async with async_session_factory() as db:
        await refresh_item_hash_statuses(db, batch_id)
        await db.commit()

    return {"ok": True, "batch_id": str(batch_id), "items": len(entries)}


async def refresh_item_hash_statuses(db: AsyncSession, batch_id: UUID | None = None) -> int:
    """Move hashing → ready/failed based on linked fingerprint status."""
    query = select(BulkSubmissionItem).where(
        BulkSubmissionItem.status == BulkSubmissionItemStatus.HASHING,
        BulkSubmissionItem.fingerprint_id.is_not(None),
    )
    if batch_id is not None:
        query = query.where(BulkSubmissionItem.batch_id == batch_id)
    result = await db.execute(query)
    updated = 0
    for item in result.scalars().all():
        fp = await db.get(MediaFingerprint, item.fingerprint_id)
        if not fp:
            continue
        if fp.status == FingerprintStatus.COMPLETED:
            item.status = BulkSubmissionItemStatus.READY
            updated += 1
        elif fp.status == FingerprintStatus.FAILED:
            item.status = BulkSubmissionItemStatus.FAILED
            item.error_message = fp.error_message or "Fingerprint failed"
            updated += 1
    return updated


async def list_owner_batches(db: AsyncSession, owner_id: UUID) -> list[BulkSubmissionBatch]:
    result = await db.execute(
        select(BulkSubmissionBatch)
        .where(BulkSubmissionBatch.owner_id == owner_id)
        .order_by(BulkSubmissionBatch.created_at.desc())
    )
    return list(result.scalars().all())


async def list_owner_items(
    db: AsyncSession,
    owner_id: UUID,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[BulkSubmissionItem]:
    await refresh_item_hash_statuses(db)
    query = select(BulkSubmissionItem).where(BulkSubmissionItem.owner_id == owner_id)
    if status:
        query = query.where(BulkSubmissionItem.status == BulkSubmissionItemStatus(status))
    else:
        query = query.where(
            BulkSubmissionItem.status.in_(
                [
                    BulkSubmissionItemStatus.PENDING_META,
                    BulkSubmissionItemStatus.HASHING,
                    BulkSubmissionItemStatus.READY,
                    BulkSubmissionItemStatus.FAILED,
                    BulkSubmissionItemStatus.DUPLICATE,
                ]
            )
        )
    result = await db.execute(
        query.order_by(BulkSubmissionItem.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def get_owner_item(
    db: AsyncSession, owner_id: UUID, item_id: UUID
) -> BulkSubmissionItem | None:
    await refresh_item_hash_statuses(db)
    result = await db.execute(
        select(BulkSubmissionItem)
        .options(selectinload(BulkSubmissionItem.batch))
        .where(BulkSubmissionItem.id == item_id, BulkSubmissionItem.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


def item_to_dict(item: BulkSubmissionItem) -> dict[str, Any]:
    meta = item.extra_data or {}
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "youtube_id": item.youtube_id,
        "youtube_url": item.youtube_url,
        "position": item.position,
        "status": item.status.value,
        "title": meta.get("title") or meta.get("youtube_title"),
        "metadata": meta,
        "fingerprint_id": item.fingerprint_id,
        "edit_id": item.edit_id,
        "error_message": item.error_message,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def batch_to_dict(batch: BulkSubmissionBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "playlist_url": batch.playlist_url,
        "playlist_id": batch.playlist_id,
        "playlist_title": batch.playlist_title,
        "status": batch.status.value,
        "item_count": batch.item_count,
        "error_message": batch.error_message,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }


async def skip_item(db: AsyncSession, item: BulkSubmissionItem) -> BulkSubmissionItem:
    if item.status == BulkSubmissionItemStatus.SUBMITTED:
        raise ValueError("Item already submitted")
    item.status = BulkSubmissionItemStatus.SKIPPED
    item.updated_at = datetime.now(UTC)
    return item


async def rehash_item(db: AsyncSession, item: BulkSubmissionItem) -> BulkSubmissionItem:
    if item.status == BulkSubmissionItemStatus.SUBMITTED:
        raise ValueError("Item already submitted")
    if item.status == BulkSubmissionItemStatus.DUPLICATE:
        raise ValueError("Item is a catalog duplicate")

    fp = MediaFingerprint(
        edit_id=None,
        youtube_id=item.youtube_id,
        phase=FingerprintPhase.PREVIEW,
        status=FingerprintStatus.PENDING,
    )
    db.add(fp)
    await db.flush()
    item.fingerprint_id = fp.id
    item.status = BulkSubmissionItemStatus.HASHING
    item.error_message = None
    item.updated_at = datetime.now(UTC)
    await db.flush()
    await enqueue_hash_job(fp.id)
    return item


async def finalize_bulk_item(
    db: AsyncSession,
    user: User,
    item: BulkSubmissionItem,
    submit_payload: dict[str, Any],
) -> Edit:
    """Create a normal CREATE_VIDEO edit from a ready staging item."""
    from app.services import EditService
    from app.services.advertisers import resolve_commercial_advertiser
    from app.services.submission_terms import validate_and_record_terms_acceptance

    if item.status not in {
        BulkSubmissionItemStatus.READY,
        BulkSubmissionItemStatus.HASHING,
        BulkSubmissionItemStatus.FAILED,
    }:
        raise ValueError(f"Item cannot be submitted in status {item.status.value}")

    # Allow submit when hash still pending only if fingerprint completed meanwhile.
    await refresh_item_hash_statuses(db)
    await db.refresh(item)
    if item.status != BulkSubmissionItemStatus.READY:
        # Still allow if fingerprint completed
        if item.fingerprint_id:
            fp = await db.get(MediaFingerprint, item.fingerprint_id)
            if not fp or fp.status != FingerprintStatus.COMPLETED:
                raise ValueError("Item fingerprint is not ready yet")
            item.status = BulkSubmissionItemStatus.READY
        else:
            raise ValueError("Item is not ready")

    terms_agreed = bool(submit_payload.get("terms_agreed"))
    await validate_and_record_terms_acceptance(db, user, terms_agreed)

    meta = item.extra_data or {}
    tags = ensure_bulk_imported_tag(submit_payload.get("tags") or meta.get("tags") or [])

    commercial_id = submit_payload.get("commercial_id")
    commercial = submit_payload.get("commercial")
    if commercial_id and commercial:
        raise ValueError("Provide either commercial_id or commercial, not both")
    if not commercial_id and not commercial:
        raise ValueError("Either commercial_id or commercial metadata is required")

    after_state: dict[str, Any] = {
        "youtube_id": item.youtube_id,
        "youtube_url": item.youtube_url,
        "thumbnail_url": submit_payload.get("thumbnail_url") or meta.get("thumbnail_url"),
        "channel_name": submit_payload.get("channel_name") or meta.get("channel_name"),
        "upload_date": submit_payload.get("upload_date") or meta.get("upload_date"),
        "duration_ms": submit_payload.get("duration_ms") or meta.get("duration_ms"),
        "aspect_ratio": submit_payload.get("aspect_ratio") or meta.get("aspect_ratio"),
        "resolution": submit_payload.get("resolution") or meta.get("resolution"),
        "language": submit_payload.get("language") or meta.get("language"),
        "region": submit_payload.get("region"),
        "sub_region": submit_payload.get("sub_region"),
        "market": submit_payload.get("market"),
        "first_aired_date": submit_payload.get("first_aired_date"),
        "last_aired_date": submit_payload.get("last_aired_date"),
        "network": submit_payload.get("network"),
        "transcript": submit_payload.get("transcript") or meta.get("transcript"),
        "slogan": submit_payload.get("slogan"),
        "cta_text": submit_payload.get("cta_text"),
        "version_label": submit_payload.get("version_label"),
        "metadata": submit_payload.get("metadata") or meta.get("metadata") or {},
        "credits": submit_payload.get("credits") or [],
        "tags": tags,
        "genres": submit_payload.get("genres"),
        "bulk_imported": True,
        "was_bulk_imported": True,
        "bulk_fingerprint_id": str(item.fingerprint_id) if item.fingerprint_id else None,
    }

    if commercial_id:
        after_state["commercial_id"] = str(commercial_id)
    if commercial:
        if isinstance(commercial, dict):
            commercial_data = dict(commercial)
        else:
            commercial_data = commercial
        commercial_data["was_bulk_imported"] = True
        resolved = await resolve_commercial_advertiser(
            db,
            user,
            commercial_data,
            brand_comment=submit_payload.get("comment"),
        )
        after_state["commercial"] = resolved.commercial
        if resolved.brand_edit:
            after_state["brand_edit_id"] = str(resolved.brand_edit.id)

    # Attach fingerprint to upcoming edit before create when possible.
    edit = await EditService.create_edit(
        db,
        user,
        EditType.CREATE_VIDEO,
        "video",
        after_state,
        comment=submit_payload.get("comment"),
        force_votable=bool(submit_payload.get("force_votable")),
    )

    if item.fingerprint_id:
        fp = await db.get(MediaFingerprint, item.fingerprint_id)
        if fp:
            fp.edit_id = edit.id
            applied = edit.status in {
                EditStatus.APPLIED,
                EditStatus.AUTOMATICALLY_APPLIED,
            }
            if applied and edit.entity_id and fp.status == FingerprintStatus.COMPLETED:
                await _copy_to_video(db, edit.entity_id, fp)
                fp.video_id = edit.entity_id

    item.status = BulkSubmissionItemStatus.SUBMITTED
    item.edit_id = edit.id
    item.updated_at = datetime.now(UTC)
    return edit
