"""Public + edit APIs for Store / Service / Event / Holiday catalogs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user_optional, require_submitter
from app.database import get_db
from app.models import CatalogStatus, Commercial, LogoPopularityChoice, User
from app.schemas import (
    AdvertiserLogoPopularityVoteCreate,
    CatalogEntityDetail,
    CatalogLogoMetadataUpdate,
    CatalogLogoPublic,
    CatalogMetadataUpdate,
    CommercialPublic,
    EditPublic,
    PaginatedResponse,
)
from app.services import EditService
from app.services.catalog import (
    ALL_CATALOG_KINDS,
    CatalogKind,
    entity_public_dict,
    entity_to_state,
    metadata_snapshot_changed,
    resolve_alias_links,
)
from app.services.catalog_logos import (
    cast_logo_popularity_vote,
    get_logo_for_entity,
    list_logos,
)
from app.services.edit_response import build_edit_public
from app.services.logo_metadata import metadata_snapshot_changed as logo_meta_changed
from app.services.logo_storage import discard_staged_logo, stage_logo
from app.services.rate_limit import check_rate_limit

router = APIRouter(tags=["catalog"])

PLURAL = {
    "store": "stores",
    "service": "services",
    "event": "events",
    "holiday": "holidays",
}


async def _get_approved(db: AsyncSession, kind: CatalogKind, sbid: UUID):
    entity = await db.get(kind.model, sbid)
    if not entity or entity.status != CatalogStatus.APPROVED:
        raise HTTPException(status_code=404, detail=f"{kind.label} not found")
    return entity


def _register_kind(kind: CatalogKind) -> None:
    prefix = f"/{PLURAL[kind.key]}"

    @router.get(prefix, response_model=PaginatedResponse)
    async def list_entities(
        request: Request,
        q: str = Query(default="", max_length=255),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, le=100),
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_current_user_optional)
    ):
        await check_rate_limit(request, user is not None)
        model = kind.model
        stmt = select(model).where(model.status == CatalogStatus.APPROVED)
        count_stmt = (
            select(func.count())
            .select_from(model)
            .where(model.status == CatalogStatus.APPROVED)
        )
        if q.strip():
            pattern = f"%{q.strip()}%"
            alias_match = func.coalesce(model.extra_data["aliases"].astext, "").ilike(pattern)
            stmt = stmt.where(or_(model.name.ilike(pattern), alias_match))
            count_stmt = count_stmt.where(or_(model.name.ilike(pattern), alias_match))
        total = (await db.execute(count_stmt)).scalar() or 0
        result = await db.execute(stmt.order_by(model.name).offset(offset).limit(limit))
        items = [entity_public_dict(kind, row) for row in result.scalars().all()]
        return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)

    list_entities.__name__ = f"list_{kind.key}s"
    list_entities.__qualname__ = list_entities.__name__

    @router.get(f"{prefix}/{{sbid}}", response_model=CatalogEntityDetail)
    async def get_entity(
        sbid: UUID,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_current_user_optional)
    ):
        await check_rate_limit(request, user is not None)
        entity = await _get_approved(db, kind, sbid)
        fk_col = getattr(Commercial, kind.id_key)
        commercials_result = await db.execute(
            select(Commercial).where(fk_col == entity.sbid).order_by(Commercial.title).limit(100)
        )
        commercials = [
            CommercialPublic.model_validate(c) for c in commercials_result.scalars().all()
        ]
        aliases = (entity.extra_data or {}).get("aliases") or []
        alias_links = await resolve_alias_links(db, kind, aliases, exclude_sbid=entity.sbid)
        return CatalogEntityDetail(
            **entity_public_dict(kind, entity),
            commercials=commercials,
            alias_links=alias_links,
        )

    get_entity.__name__ = f"get_{kind.key}"
    get_entity.__qualname__ = get_entity.__name__

    @router.post(f"{prefix}/{{sbid}}/submit-metadata", response_model=EditPublic, status_code=201)
    async def submit_metadata(
        sbid: UUID,
        body: CatalogMetadataUpdate,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_submitter)
    ):
        entity = await _get_approved(db, kind, sbid)
        before = entity_to_state(kind, entity)
        payload = body.model_dump(exclude_unset=True)
        after = {**before, **payload, kind.id_key: str(entity.sbid), "name": entity.name}
        if not metadata_snapshot_changed(kind, before, after):
            raise HTTPException(status_code=400, detail="No metadata changes to submit")
        try:
            edit = await EditService.create_edit(
                db,
                user,
                kind.edit_edit,
                kind.entity_type,
                after,
                before_state=before,
                entity_id=entity.sbid,
                comment=f'Proposed metadata update for {kind.label.lower()} "{entity.name}".',
                force_votable=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        await db.refresh(edit, ["votes"])
        return await build_edit_public(db, edit, editor_username=user.username)

    submit_metadata.__name__ = f"submit_{kind.key}_metadata"
    submit_metadata.__qualname__ = submit_metadata.__name__

    @router.post(f"{prefix}/{{sbid}}/submit-logo", response_model=EditPublic, status_code=201)
    async def submit_logo(
        sbid: UUID,
        file: UploadFile = File(...),
        label: str | None = Form(default=None),
        year: int | None = Form(default=None),
        month: int | None = Form(default=None),
        event: str | None = Form(default=None),
        notes: str | None = Form(default=None),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_submitter)
    ):
        entity = await _get_approved(db, kind, sbid)
        data = await file.read()
        try:
            staging_file, logo_url = stage_logo(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        after_state = {
            kind.id_key: str(entity.sbid),
            "logo_url": logo_url,
            "logo_staging_file": staging_file,
            "label": label,
            "year": year,
            "month": month,
            "event": event,
            "notes": notes,
        }
        try:
            edit = await EditService.create_edit(
                db,
                user,
                kind.add_logo_edit,
                kind.entity_type,
                after_state,
                entity_id=entity.sbid,
                comment=f'Proposed logo for {kind.label.lower()} "{entity.name}".',
                force_votable=True,
            )
        except ValueError as exc:
            discard_staged_logo(staging_file)
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        await db.refresh(edit, ["votes"])
        return await build_edit_public(db, edit, editor_username=user.username)

    submit_logo.__name__ = f"submit_{kind.key}_logo"
    submit_logo.__qualname__ = submit_logo.__name__

    @router.get(f"{prefix}/{{sbid}}/logos", response_model=list[CatalogLogoPublic])
    async def get_logos(
        sbid: UUID,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_current_user_optional)
    ):
        await check_rate_limit(request, user is not None)
        await _get_approved(db, kind, sbid)
        rows = await list_logos(db, kind, sbid, viewer=user)
        return [CatalogLogoPublic(**row) for row in rows]

    get_logos.__name__ = f"get_{kind.key}_logos"
    get_logos.__qualname__ = get_logos.__name__

    @router.post(f"{prefix}/{{sbid}}/logos/{{logo_id}}/popularity-vote")
    async def vote_logo(
        sbid: UUID,
        logo_id: UUID,
        body: AdvertiserLogoPopularityVoteCreate,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_submitter)
    ):
        await _get_approved(db, kind, sbid)
        logo = await get_logo_for_entity(db, kind, sbid, logo_id)
        if not logo:
            raise HTTPException(status_code=404, detail="Logo not found")
        choice = None if body.choice is None else LogoPopularityChoice(body.choice)
        await cast_logo_popularity_vote(db, kind, logo, user, choice)
        rows = await list_logos(db, kind, sbid, viewer=user)
        return next((r for r in rows if r["id"] == logo_id), None)

    vote_logo.__name__ = f"vote_{kind.key}_logo"
    vote_logo.__qualname__ = vote_logo.__name__

    @router.post(
        f"{prefix}/{{sbid}}/logos/{{logo_id}}/submit-metadata",
        response_model=EditPublic,
        status_code=201,
    )
    async def submit_logo_metadata(
        sbid: UUID,
        logo_id: UUID,
        body: CatalogLogoMetadataUpdate,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_submitter)
    ):
        await _get_approved(db, kind, sbid)
        logo = await get_logo_for_entity(db, kind, sbid, logo_id)
        if not logo:
            raise HTTPException(status_code=404, detail="Logo not found")
        before = {
            "logo_id": str(logo.id),
            kind.id_key: str(sbid),
            "label": logo.label,
            "year": logo.year,
            "month": logo.month,
            "event": getattr(logo, "event_label", None) or getattr(logo, "event", None),
            "notes": logo.notes,
        }
        before = {k: v for k, v in before.items() if v not in (None, "")}
        payload = body.model_dump(exclude_unset=True)
        after = {**before, **payload, "logo_id": str(logo.id), kind.id_key: str(sbid)}
        if not logo_meta_changed(before, after):
            raise HTTPException(status_code=400, detail="No logo metadata changes to submit")
        try:
            edit = await EditService.create_edit(
                db,
                user,
                kind.edit_logo_edit,
                f"{kind.entity_type}_logo",
                after,
                before_state=before,
                entity_id=logo.id,
                comment="Proposed logo metadata update.",
                force_votable=True,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        await db.refresh(edit, ["votes"])
        return await build_edit_public(db, edit, editor_username=user.username)

    submit_logo_metadata.__name__ = f"submit_{kind.key}_logo_metadata"
    submit_logo_metadata.__qualname__ = submit_logo_metadata.__name__


for _kind in ALL_CATALOG_KINDS:
    _register_kind(_kind)
