"""Serve uploaded media and accept custom video thumbnail / brand logo submissions."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_submitter
from app.database import get_db
from app.models import Advertiser, AdvertiserStatus, EditType, User, Video, VideoVisibility
from app.schemas import AdvertiserMetadataUpdate, EditPublic
from app.services import EditService, SearchService
from app.services.advertiser_metadata import (
    advertiser_to_state,
    metadata_snapshot_changed,
)
from app.services.edit_response import build_edit_public
from app.services.logo_storage import (
    discard_staged_logo,
    logo_media_type,
    resolve_logo_path,
    stage_logo,
)
from app.services.thumbnail_storage import (
    discard_staged_thumbnail,
    resolve_media_path,
    stage_thumbnail,
)

router = APIRouter(tags=["media"])


def _optional_form_int(value: str | None, *, field: str, min_v: int, max_v: int) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = int(str(value).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be a number") from exc
    if parsed < min_v or parsed > max_v:
        raise HTTPException(status_code=400, detail=f"{field} must be between {min_v} and {max_v}")
    return parsed


@router.get("/media/thumbnails/{relative_path:path}")
async def get_thumbnail(relative_path: str):
    path = resolve_media_path(relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    media_type = "image/jpeg"
    if path.suffix.lower() == ".png":
        media_type = "image/png"
    elif path.suffix.lower() == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/media/logos/{relative_path:path}")
async def get_logo(relative_path: str):
    path = resolve_logo_path(relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="Logo not found")

    return FileResponse(
        path,
        media_type=logo_media_type(path),
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/videos/{sbid}/submit-thumbnail", response_model=EditPublic, status_code=201)
async def submit_video_thumbnail(
    sbid: UUID,
    file: UploadFile = File(...),
    comment: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    video = await SearchService.get_video_detail(db, sbid, include_hidden=True)
    if not video or video.visibility == VideoVisibility.REMOVED:
        raise HTTPException(status_code=404, detail="Video not found")

    data = await file.read()
    try:
        staging_file, preview_url = stage_thumbnail(data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    before_state = {"thumbnail_url": video.thumbnail_url}
    after_state = {
        "thumbnail_url": preview_url,
        "thumbnail_staging_file": staging_file,
    }

    try:
        edit = await EditService.create_edit(
            db,
            user,
            EditType.EDIT_VIDEO,
            "video",
            after_state,
            before_state=before_state,
            entity_id=video.sbid,
            comment=comment or "Proposed custom thumbnail image.",
            force_votable=True,
        )
    except ValueError as exc:
        discard_staged_thumbnail(staging_file)
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    await db.refresh(edit, ["votes"])
    return await build_edit_public(db, edit)


@router.post("/advertisers/{sbid}/submit-logo", response_model=EditPublic, status_code=201)
async def submit_advertiser_logo(
    sbid: UUID,
    file: UploadFile = File(...),
    comment: str | None = Form(default=None),
    label: str | None = Form(default=None),
    year: str | None = Form(default=None),
    month: str | None = Form(default=None),
    event: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    result = await db.execute(select(Advertiser).where(Advertiser.sbid == sbid))
    advertiser = result.scalar_one_or_none()
    if not advertiser or advertiser.status != AdvertiserStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved brand not found")

    parsed_year = _optional_form_int(year, field="year", min_v=1800, max_v=2100)
    parsed_month = _optional_form_int(month, field="month", min_v=1, max_v=12)

    data = await file.read()
    try:
        staging_file, preview_url = stage_logo(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    after_state = {
        "logo_url": preview_url,
        "logo_staging_file": staging_file,
        "advertiser_id": str(advertiser.sbid),
        "label": label.strip() if label and label.strip() else None,
        "year": parsed_year,
        "month": parsed_month,
        "event": event.strip() if event and event.strip() else None,
        "notes": notes.strip() if notes and notes.strip() else None,
    }
    after_state = {k: v for k, v in after_state.items() if v is not None}

    context_bits = [part for part in (after_state.get("label"), after_state.get("event")) if part]
    if parsed_year is not None:
        date_label = str(parsed_year)
        if parsed_month is not None:
            date_label = f"{parsed_year}-{parsed_month:02d}"
        context_bits.append(date_label)
    context = " · ".join(context_bits) if context_bits else "new logo version"

    try:
        edit = await EditService.create_edit(
            db,
            user,
            EditType.ADD_ADVERTISER_LOGO,
            "advertiser",
            after_state,
            before_state={},
            entity_id=advertiser.sbid,
            comment=comment or f'Proposed {context} for "{advertiser.name}".',
            force_votable=True,
        )
    except ValueError as exc:
        discard_staged_logo(staging_file)
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    await db.refresh(edit, ["votes"])
    return await build_edit_public(db, edit)


@router.post("/advertisers/{sbid}/submit-metadata", response_model=EditPublic, status_code=201)
async def submit_advertiser_metadata(
    sbid: UUID,
    body: AdvertiserMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_submitter),
):
    result = await db.execute(select(Advertiser).where(Advertiser.sbid == sbid))
    advertiser = result.scalar_one_or_none()
    if not advertiser or advertiser.status != AdvertiserStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Approved brand not found")

    before_state = advertiser_to_state(advertiser)
    payload = body.model_dump()
    for key in ("aliases", "social"):
        if key in payload and not payload[key] and not before_state.get(key):
            payload.pop(key, None)
    for key, value in list(payload.items()):
        if isinstance(value, str) and not value.strip():
            payload[key] = None
    after_state = {**before_state, **payload, "advertiser_id": str(advertiser.sbid)}
    if not metadata_snapshot_changed(before_state, after_state):
        raise HTTPException(status_code=400, detail="No metadata changes to submit")

    try:
        edit = await EditService.create_edit(
            db,
            user,
            EditType.EDIT_ADVERTISER,
            "advertiser",
            after_state,
            before_state=before_state,
            entity_id=advertiser.sbid,
            comment=f'Proposed metadata update for "{advertiser.name}".',
            force_votable=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    await db.refresh(edit, ["votes"])
    return await build_edit_public(db, edit)
