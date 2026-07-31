"""Bulk playlist staging: import, hash, and finalize into normal video edits."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import func, select
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


# Items that occupy a staging/review slot (counted toward the window).
_STAGING_STATUSES = (
    BulkSubmissionItemStatus.PENDING_META,
    BulkSubmissionItemStatus.HASHING,
    BulkSubmissionItemStatus.READY,
    BulkSubmissionItemStatus.FAILED,
)

# Items that block re-import of the same YouTube id for this owner.
_OPEN_QUEUE_STATUSES = (
    BulkSubmissionItemStatus.QUEUED,
    *_STAGING_STATUSES,
)


async def _catalog_video_ids(db: AsyncSession, youtube_ids: list[str]) -> dict[str, UUID]:
    if not youtube_ids:
        return {}
    result = await db.execute(
        select(Video.youtube_id, Video.sbid).where(Video.youtube_id.in_(youtube_ids))
    )
    return {row[0]: row[1] for row in result.all()}


async def _open_queue_youtube_ids(
    db: AsyncSession, owner_id: UUID, youtube_ids: list[str]
) -> set[str]:
    if not youtube_ids:
        return set()
    result = await db.execute(
        select(BulkSubmissionItem.youtube_id).where(
            BulkSubmissionItem.owner_id == owner_id,
            BulkSubmissionItem.youtube_id.in_(youtube_ids),
            BulkSubmissionItem.status.in_(_OPEN_QUEUE_STATUSES),
        )
    )
    return {row[0] for row in result.all()}


async def classify_playlist_entries(
    db: AsyncSession,
    owner_id: UUID,
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Classify playlist entries before import/hashing.

    Reasons: ok | catalog | queue | playlist_duplicate
    """
    youtube_ids = [e["youtube_id"] for e in entries if e.get("youtube_id")]
    catalog = await _catalog_video_ids(db, youtube_ids)
    queued = await _open_queue_youtube_ids(db, owner_id, youtube_ids)

    seen_in_playlist: set[str] = set()
    classified: list[dict[str, Any]] = []
    for entry in entries:
        youtube_id = entry["youtube_id"]
        row = {
            "youtube_id": youtube_id,
            "youtube_url": entry.get("youtube_url") or youtube_watch_url(youtube_id),
            "title": entry.get("title"),
            "position": int(entry.get("position") or 0),
            "status": "ok",
            "reason": None,
            "existing_video_sbid": None,
        }
        if youtube_id in seen_in_playlist:
            row["status"] = "duplicate"
            row["reason"] = "playlist_duplicate"
        elif youtube_id in catalog:
            row["status"] = "duplicate"
            row["reason"] = "catalog"
            row["existing_video_sbid"] = str(catalog[youtube_id])
        elif youtube_id in queued:
            row["status"] = "duplicate"
            row["reason"] = "queue"
        else:
            seen_in_playlist.add(youtube_id)
        classified.append(row)
    return classified


async def preview_playlist_duplicates(
    db: AsyncSession,
    owner: User,
    playlist_url: str,
) -> dict[str, Any]:
    """Expand playlist and classify duplicates without creating a batch."""
    expanded = expand_youtube_playlist(
        playlist_url.strip(),
        max_items=settings.bulk_submit_max_playlist_items,
    )
    entries = expanded.get("entries") or []
    classified = await classify_playlist_entries(db, owner.id, entries)
    counts = {
        "total": len(classified),
        "ok": 0,
        "catalog": 0,
        "queue": 0,
        "playlist_duplicate": 0,
    }
    for row in classified:
        if row["status"] == "ok":
            counts["ok"] += 1
        elif row["reason"] in counts:
            counts[row["reason"]] += 1
    return {
        "playlist_id": expanded.get("playlist_id"),
        "playlist_title": expanded.get("playlist_title"),
        "playlist_url": playlist_url.strip(),
        "counts": counts,
        "entries": classified,
        "staging_window": settings.bulk_submit_staging_window,
    }


def normalize_bulk_defaults(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Drop empty values so review UI only applies intentional playlist defaults."""
    if not raw:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            cleaned[key] = text
            continue
        if isinstance(value, list):
            items = [str(v).strip() for v in value if str(v).strip()]
            if items:
                cleaned[key] = items
            continue
        cleaned[key] = value
    return cleaned


async def create_bulk_batch(
    db: AsyncSession,
    owner: User,
    playlist_url: str,
    *,
    defaults: dict[str, Any] | None = None,
) -> BulkSubmissionBatch:
    batch = BulkSubmissionBatch(
        owner_id=owner.id,
        playlist_url=playlist_url.strip(),
        status=BulkSubmissionBatchStatus.IMPORTING,
        defaults=normalize_bulk_defaults(defaults),
    )
    db.add(batch)
    await db.flush()
    return batch


async def _count_batch_status(
    db: AsyncSession, batch_id: UUID, statuses: tuple[BulkSubmissionItemStatus, ...]
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(BulkSubmissionItem)
        .where(
            BulkSubmissionItem.batch_id == batch_id,
            BulkSubmissionItem.status.in_(statuses),
        )
    )
    return int(result.scalar() or 0)


async def _stage_item(db: AsyncSession, item: BulkSubmissionItem) -> UUID | None:
    """
    Promote one queued item into the review window and start hashing.

    YouTube metadata is enriched asynchronously after staging so the review form
    can open with prefetched data without blocking this step.
    Returns fingerprint id to enqueue after commit, or None on failure.
    """
    try:
        prior = dict(item.extra_data or {})
        prior.pop("meta_fetched", None)
        prior.pop("meta_error", None)
        item.extra_data = prior
        item.status = BulkSubmissionItemStatus.HASHING
        fp = MediaFingerprint(
            edit_id=None,
            youtube_id=item.youtube_id,
            phase=FingerprintPhase.PREVIEW,
            status=FingerprintStatus.PENDING,
        )
        db.add(fp)
        await db.flush()
        item.fingerprint_id = fp.id
        item.error_message = None
        item.updated_at = datetime.now(UTC)
        return fp.id
    except Exception as exc:  # noqa: BLE001
        item.status = BulkSubmissionItemStatus.FAILED
        item.error_message = str(exc)[:500]
        item.updated_at = datetime.now(UTC)
        return None


def item_metadata_ready(extra: dict[str, Any] | None) -> bool:
    """True when staged item has review-ready YouTube metadata."""
    data = extra or {}
    if data.get("meta_fetched"):
        return True
    # Legacy sync staging stored a full fetch_youtube_metadata payload.
    return bool(
        data.get("channel_name")
        or data.get("duration_ms")
        or data.get("thumbnail_url")
        or (isinstance(data.get("metadata"), dict) and data["metadata"].get("youtube_title"))
    )


async def enqueue_bulk_item_enrich(item_id: UUID) -> None:
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("enrich_bulk_item_metadata", str(item_id))
    finally:
        await pool.aclose()


async def enrich_bulk_item_metadata(item_id: UUID) -> dict[str, Any]:
    """Worker: fetch YouTube metadata for a staged review item in the background."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        item = await db.get(BulkSubmissionItem, item_id)
        if not item:
            return {"ok": False, "error": "item not found"}
        if item.status in {
            BulkSubmissionItemStatus.QUEUED,
            BulkSubmissionItemStatus.SUBMITTED,
            BulkSubmissionItemStatus.SKIPPED,
            BulkSubmissionItemStatus.DUPLICATE,
        }:
            return {"ok": False, "error": f"item status {item.status.value}"}
        if item_metadata_ready(item.extra_data):
            return {"ok": True, "skipped": True, "item_id": str(item_id)}

        prior = dict(item.extra_data or {})
        try:
            meta = await asyncio.to_thread(fetch_youtube_metadata, item.youtube_id)
            if not meta.get("title") and not meta.get("youtube_title") and prior.get("title"):
                meta = {**meta, "title": prior["title"]}
            existing = await db.scalar(
                select(Video.sbid).where(Video.youtube_id == item.youtube_id)
            )
            if existing:
                meta["existing_video_sbid"] = str(existing)
            meta["meta_fetched"] = True
            meta.pop("meta_error", None)
            item.extra_data = meta
            item.updated_at = datetime.now(UTC)
            await db.commit()
            return {"ok": True, "item_id": str(item_id)}
        except Exception as exc:  # noqa: BLE001
            prior["meta_error"] = str(exc)[:500]
            prior["meta_fetched"] = False
            item.extra_data = prior
            item.updated_at = datetime.now(UTC)
            await db.commit()
            logger.warning("Bulk item metadata enrich failed for %s: %s", item_id, exc)
            return {"ok": False, "error": str(exc)[:500], "item_id": str(item_id)}


async def stage_next_bulk_items(
    db: AsyncSession,
    batch_id: UUID,
    *,
    limit: int | None = None,
) -> tuple[list[UUID], list[UUID]]:
    """
    Fill the per-batch staging window from QUEUED playlist links.

    Hashing starts when an item is promoted into the window. YouTube metadata is
    enriched in the background afterward.
    Returns (fingerprint ids to enqueue, staged item ids to enrich).
    """
    window = max(1, int(settings.bulk_submit_staging_window))
    active = await _count_batch_status(db, batch_id, _STAGING_STATUSES)
    slots = max(0, window - active)
    if limit is not None:
        slots = min(slots, max(0, int(limit)))
    if slots == 0:
        return [], []

    result = await db.execute(
        select(BulkSubmissionItem)
        .where(
            BulkSubmissionItem.batch_id == batch_id,
            BulkSubmissionItem.status == BulkSubmissionItemStatus.QUEUED,
        )
        .order_by(BulkSubmissionItem.position.asc(), BulkSubmissionItem.created_at.asc())
        .limit(slots)
        .with_for_update(skip_locked=True)
    )
    fingerprint_ids: list[UUID] = []
    staged_item_ids: list[UUID] = []
    for item in result.scalars().all():
        fp_id = await _stage_item(db, item)
        staged_item_ids.append(item.id)
        if fp_id is not None:
            fingerprint_ids.append(fp_id)
    return fingerprint_ids, staged_item_ids


async def import_bulk_playlist(batch_id: UUID) -> dict[str, Any]:
    """Worker entry: store full playlist link list, stage the review window, enqueue hashes."""
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
        classified = await classify_playlist_entries(db, batch.owner_id, entries)
        batch.item_count = len(classified)
        await db.flush()

        for row in classified:
            youtube_id = row["youtube_id"]
            item = BulkSubmissionItem(
                batch_id=batch.id,
                owner_id=batch.owner_id,
                youtube_id=youtube_id,
                youtube_url=row["youtube_url"],
                position=row["position"],
                status=BulkSubmissionItemStatus.QUEUED,
                extra_data={"title": row.get("title")},
            )
            db.add(item)
            await db.flush()

            if row["status"] == "duplicate":
                item.status = BulkSubmissionItemStatus.DUPLICATE
                reason = row.get("reason") or "duplicate"
                messages = {
                    "catalog": "Already in catalog",
                    "queue": "Already in your review queue",
                    "playlist_duplicate": "Duplicate entry in this playlist",
                }
                item.error_message = messages.get(reason, "Duplicate link")
                extra = dict(item.extra_data or {})
                extra["duplicate_reason"] = reason
                if row.get("existing_video_sbid"):
                    extra["existing_video_sbid"] = row["existing_video_sbid"]
                item.extra_data = extra

        fingerprint_ids, staged_item_ids = await stage_next_bulk_items(db, batch.id)
        batch.status = BulkSubmissionBatchStatus.READY
        batch.updated_at = datetime.now(UTC)
        await db.commit()

    for fp_id in fingerprint_ids:
        await enqueue_hash_job(fp_id)
    for item_id in staged_item_ids:
        await enqueue_bulk_item_enrich(item_id)

    async with async_session_factory() as db:
        await refresh_item_hash_statuses(db, batch_id)
        await db.commit()

    return {
        "ok": True,
        "batch_id": str(batch_id),
        "items": len(classified),
        "staged": len(fingerprint_ids),
        "staging_window": settings.bulk_submit_staging_window,
    }


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


async def get_owner_batch(
    db: AsyncSession, owner_id: UUID, batch_id: UUID
) -> BulkSubmissionBatch | None:
    result = await db.execute(
        select(BulkSubmissionBatch)
        .options(selectinload(BulkSubmissionBatch.items))
        .where(BulkSubmissionBatch.id == batch_id, BulkSubmissionBatch.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def cancel_bulk_batch(
    db: AsyncSession, owner_id: UUID, batch_id: UUID
) -> BulkSubmissionBatch | None:
    """
    Cancel a bulk playlist import: remove the batch and its staging/queue items.

    Already-submitted catalog edits and videos are left intact. Preview fingerprints
    that were never attached to an edit are cleaned up.
    """
    batch = await get_owner_batch(db, owner_id, batch_id)
    if not batch:
        return None

    fingerprint_ids = [
        item.fingerprint_id for item in batch.items if item.fingerprint_id is not None
    ]
    await db.delete(batch)
    await db.flush()

    for fp_id in fingerprint_ids:
        fp = await db.get(MediaFingerprint, fp_id)
        if fp is not None and fp.edit_id is None:
            await db.delete(fp)

    return batch


async def list_owner_items(
    db: AsyncSession,
    owner_id: UUID,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[BulkSubmissionItem]:
    await refresh_item_hash_statuses(db)
    query = select(BulkSubmissionItem).options(
        selectinload(BulkSubmissionItem.batch)
    ).where(BulkSubmissionItem.owner_id == owner_id)
    if status:
        query = query.where(BulkSubmissionItem.status == BulkSubmissionItemStatus(status))
    else:
        # Default review queue: active staging slots only (not the waiting link list).
        query = query.where(BulkSubmissionItem.status.in_(list(_STAGING_STATUSES)))
    result = await db.execute(
        query.order_by(
            BulkSubmissionItem.position.asc(),
            BulkSubmissionItem.created_at.asc(),
        )
        .offset(offset)
        .limit(limit)
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
    batch_defaults: dict[str, Any] = {}
    if getattr(item, "batch", None) is not None:
        batch_defaults = dict(item.batch.defaults or {})
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "youtube_id": item.youtube_id,
        "youtube_url": item.youtube_url,
        "position": item.position,
        "status": item.status.value,
        "title": meta.get("title") or meta.get("youtube_title"),
        "metadata": meta,
        "metadata_ready": item_metadata_ready(meta),
        "batch_defaults": batch_defaults,
        "fingerprint_id": item.fingerprint_id,
        "edit_id": item.edit_id,
        "error_message": item.error_message,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def batch_counts(db: AsyncSession, batch_id: UUID) -> dict[str, int]:
    queued = await _count_batch_status(db, batch_id, (BulkSubmissionItemStatus.QUEUED,))
    staging = await _count_batch_status(db, batch_id, _STAGING_STATUSES)
    return {"queued_count": queued, "staging_count": staging}


def batch_to_dict(
    batch: BulkSubmissionBatch,
    *,
    queued_count: int = 0,
    staging_count: int = 0,
) -> dict[str, Any]:
    return {
        "id": batch.id,
        "playlist_url": batch.playlist_url,
        "playlist_id": batch.playlist_id,
        "playlist_title": batch.playlist_title,
        "status": batch.status.value,
        "item_count": batch.item_count,
        "queued_count": queued_count,
        "staging_count": staging_count,
        "defaults": dict(batch.defaults or {}),
        "error_message": batch.error_message,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }


async def skip_item(db: AsyncSession, item: BulkSubmissionItem) -> tuple[list[UUID], list[UUID]]:
    """Skip an item and refill the staging window.

    Returns (fingerprint ids to enqueue, staged item ids to enrich).
    """
    if item.status == BulkSubmissionItemStatus.SUBMITTED:
        raise ValueError("Item already submitted")
    if item.status == BulkSubmissionItemStatus.QUEUED:
        raise ValueError("Queued playlist links cannot be skipped until staged")
    item.status = BulkSubmissionItemStatus.SKIPPED
    item.updated_at = datetime.now(UTC)
    return await stage_next_bulk_items(db, item.batch_id)


async def rehash_item(db: AsyncSession, item: BulkSubmissionItem) -> BulkSubmissionItem:
    if item.status == BulkSubmissionItemStatus.SUBMITTED:
        raise ValueError("Item already submitted")
    if item.status == BulkSubmissionItemStatus.DUPLICATE:
        raise ValueError("Item is a catalog duplicate")
    if item.status == BulkSubmissionItemStatus.QUEUED:
        raise ValueError("Queued playlist links are hashed when they enter the review window")

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
) -> tuple[Edit, list[UUID], list[UUID]]:
    """
    Create a normal CREATE_VIDEO edit from a staging item.

    Hashing is not required to finish first: any in-flight preview fingerprint is
    attached to the edit (and video when auto-applied) and continues in the background.
    Returns (edit, fingerprint ids to enqueue, staged item ids to enrich).
    """
    from app.services import EditService
    from app.services.advertisers import resolve_commercial_advertiser
    from app.services.submission_terms import validate_and_record_terms_acceptance

    if item.status not in {
        BulkSubmissionItemStatus.READY,
        BulkSubmissionItemStatus.HASHING,
        BulkSubmissionItemStatus.FAILED,
    }:
        raise ValueError(f"Item cannot be submitted in status {item.status.value}")

    await refresh_item_hash_statuses(db)
    await db.refresh(item)

    # Ensure a fingerprint exists so hashing can continue (or start) in the background.
    enqueue_fps: list[UUID] = []
    if not item.fingerprint_id:
        fp = MediaFingerprint(
            edit_id=None,
            youtube_id=item.youtube_id,
            phase=FingerprintPhase.PREVIEW,
            status=FingerprintStatus.PENDING,
        )
        db.add(fp)
        await db.flush()
        item.fingerprint_id = fp.id
        enqueue_fps.append(fp.id)

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
        from app.services.catalog import resolve_all_catalogs

        commercial_resolved, catalog_edits = await resolve_all_catalogs(
            db, user, resolved.commercial
        )
        after_state["commercial"] = commercial_resolved
        if resolved.brand_edit:
            after_state["brand_edit_id"] = str(resolved.brand_edit.id)
        if catalog_edits:
            after_state["catalog_edit_ids"] = [str(e.id) for e in catalog_edits]

    # Create the edit immediately; hashing continues asynchronously.
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
        if fp and fp.status == FingerprintStatus.FAILED:
            applied = edit.status in {
                EditStatus.APPLIED,
                EditStatus.AUTOMATICALLY_APPLIED,
            }
            # Auto-apply already creates a FINAL fingerprint when the preview failed.
            # For open edits, start a fresh background hash on the edit.
            if not applied:
                new_fp = MediaFingerprint(
                    edit_id=edit.id,
                    youtube_id=item.youtube_id,
                    phase=FingerprintPhase.PREVIEW,
                    status=FingerprintStatus.PENDING,
                )
                db.add(new_fp)
                await db.flush()
                item.fingerprint_id = new_fp.id
                enqueue_fps.append(new_fp.id)
        elif fp:
            fp.edit_id = edit.id
            applied = edit.status in {
                EditStatus.APPLIED,
                EditStatus.AUTOMATICALLY_APPLIED,
            }
            if applied and edit.entity_id:
                if fp.status == FingerprintStatus.COMPLETED:
                    await _copy_to_video(db, edit.entity_id, fp)
                    fp.video_id = edit.entity_id
                elif fp.status in {
                    FingerprintStatus.PENDING,
                    FingerprintStatus.PROCESSING,
                }:
                    # In-flight hash should land on the video when the worker finishes.
                    fp.video_id = edit.entity_id
                    if fp.status == FingerprintStatus.PENDING:
                        enqueue_fps.append(fp.id)
            elif fp.status == FingerprintStatus.PENDING:
                enqueue_fps.append(fp.id)

    item.status = BulkSubmissionItemStatus.SUBMITTED
    item.edit_id = edit.id
    item.updated_at = datetime.now(UTC)

    # Free a staging slot → pull the next playlist link into review + hashing.
    refill_fps, enrich_ids = await stage_next_bulk_items(db, item.batch_id)
    # Dedupe while preserving order.
    seen: set[UUID] = set()
    combined: list[UUID] = []
    for fp_id in [*enqueue_fps, *refill_fps]:
        if fp_id in seen:
            continue
        seen.add(fp_id)
        combined.append(fp_id)
    return edit, combined, enrich_ids
