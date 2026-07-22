"""Shared catalog entity registry (Store / Service / Event / Holiday)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CatalogStatus,
    Edit,
    EditType,
    Event,
    EventLogo,
    EventLogoVote,
    Holiday,
    HolidayLogo,
    HolidayLogoVote,
    Service,
    ServiceLogo,
    ServiceLogoVote,
    Store,
    StoreLogo,
    StoreLogoVote,
    User,
)
from app.services.holiday_dates import parse_holiday_date_text
from app.utils import make_unique_slug

METADATA_JSON_FIELDS = ("aliases", "tagline", "social", "notes")

SHARED_SCALAR = (
    "description",
    "website",
    "country",
    "wikipedia_url",
    "logo_url",
)


@dataclass(frozen=True)
class CatalogKind:
    key: str  # store / service / event / holiday
    label: str
    model: type
    logo_model: type
    vote_model: type
    parent_fk: str  # store_id on logo
    id_key: str  # store_id on commercial / state
    name_key: str  # store_name
    entity_type: str  # for edits entity_type field
    create_edit: EditType
    edit_edit: EditType
    add_logo_edit: EditType
    edit_logo_edit: EditType
    scalar_fields: tuple[str, ...]
    edit_keys: tuple[str, ...]


STORE = CatalogKind(
    key="store",
    label="Store",
    model=Store,
    logo_model=StoreLogo,
    vote_model=StoreLogoVote,
    parent_fk="store_id",
    id_key="store_id",
    name_key="store_name",
    entity_type="store",
    create_edit=EditType.CREATE_STORE,
    edit_edit=EditType.EDIT_STORE,
    add_logo_edit=EditType.ADD_STORE_LOGO,
    edit_logo_edit=EditType.EDIT_STORE_LOGO,
    scalar_fields=(*SHARED_SCALAR, "founded_year", "store_type", "headquarters", "parent_company"),
    edit_keys=(
        "description",
        "website",
        "country",
        "founded_year",
        "store_type",
        "headquarters",
        "parent_company",
        "wikipedia_url",
        *METADATA_JSON_FIELDS,
    ),
)

SERVICE = CatalogKind(
    key="service",
    label="Service",
    model=Service,
    logo_model=ServiceLogo,
    vote_model=ServiceLogoVote,
    parent_fk="service_id",
    id_key="service_id",
    name_key="service_name",
    entity_type="service",
    create_edit=EditType.CREATE_SERVICE,
    edit_edit=EditType.EDIT_SERVICE,
    add_logo_edit=EditType.ADD_SERVICE_LOGO,
    edit_logo_edit=EditType.EDIT_SERVICE_LOGO,
    scalar_fields=(
        *SHARED_SCALAR,
        "founded_year",
        "service_type",
        "headquarters",
        "parent_company",
    ),
    edit_keys=(
        "description",
        "website",
        "country",
        "founded_year",
        "service_type",
        "headquarters",
        "parent_company",
        "wikipedia_url",
        *METADATA_JSON_FIELDS,
    ),
)

EVENT = CatalogKind(
    key="event",
    label="Event",
    model=Event,
    logo_model=EventLogo,
    vote_model=EventLogoVote,
    parent_fk="event_id",
    id_key="event_id",
    name_key="event_name",
    entity_type="event",
    create_edit=EditType.CREATE_EVENT,
    edit_edit=EditType.EDIT_EVENT,
    add_logo_edit=EditType.ADD_EVENT_LOGO,
    edit_logo_edit=EditType.EDIT_EVENT_LOGO,
    scalar_fields=(
        *SHARED_SCALAR,
        "location",
        "start_year",
        "end_year",
        "start_date",
        "end_date",
    ),
    edit_keys=(
        "description",
        "website",
        "country",
        "location",
        "start_year",
        "end_year",
        "start_date",
        "end_date",
        "wikipedia_url",
        *METADATA_JSON_FIELDS,
    ),
)

HOLIDAY = CatalogKind(
    key="holiday",
    label="Holiday",
    model=Holiday,
    logo_model=HolidayLogo,
    vote_model=HolidayLogoVote,
    parent_fk="holiday_id",
    id_key="holiday_id",
    name_key="holiday_name",
    entity_type="holiday",
    create_edit=EditType.CREATE_HOLIDAY,
    edit_edit=EditType.EDIT_HOLIDAY,
    add_logo_edit=EditType.ADD_HOLIDAY_LOGO,
    edit_logo_edit=EditType.EDIT_HOLIDAY_LOGO,
    scalar_fields=(*SHARED_SCALAR, "date_text", "year", "month", "day"),
    edit_keys=(
        "description",
        "website",
        "country",
        "date_text",
        "year",
        "month",
        "day",
        "wikipedia_url",
        *METADATA_JSON_FIELDS,
    ),
)

CATALOG_KINDS: dict[str, CatalogKind] = {
    STORE.key: STORE,
    SERVICE.key: SERVICE,
    EVENT.key: EVENT,
    HOLIDAY.key: HOLIDAY,
}

ALL_CATALOG_KINDS = (STORE, SERVICE, EVENT, HOLIDAY)


@dataclass
class CatalogResolveResult:
    commercial: dict
    catalog_edit: Edit | None = None


def _serialize_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def entity_to_state(kind: CatalogKind, entity: Any) -> dict:
    meta = entity.extra_data or {}
    state: dict = {
        kind.id_key: str(entity.sbid),
        "name": entity.name,
        "logo_url": entity.logo_url,
        "aliases": meta.get("aliases") or [],
        "tagline": meta.get("tagline"),
        "social": meta.get("social") or {},
        "notes": meta.get("notes"),
    }
    for field in kind.scalar_fields:
        if field == "logo_url":
            continue
        state[field] = _serialize_value(getattr(entity, field, None))
    return {k: v for k, v in state.items() if v not in (None, "", [], {})}


def entity_public_dict(kind: CatalogKind, entity: Any) -> dict:
    data = {
        "sbid": entity.sbid,
        "name": entity.name,
        "slug": entity.slug,
        "description": entity.description,
        "logo_url": entity.logo_url,
        "main_logo_id": entity.main_logo_id,
        "website": entity.website,
        "country": entity.country,
        "wikipedia_url": entity.wikipedia_url,
        "metadata": entity.extra_data or {},
        "external_ids": entity.external_ids or {},
        "status": entity.status.value if entity.status else None,
        "created_at": entity.created_at,
    }
    for field in kind.scalar_fields:
        if field in data or field == "logo_url":
            continue
        data[field] = getattr(entity, field, None)
    return data


def apply_entity_state(kind: CatalogKind, entity: Any, state: dict) -> None:
    for field in kind.scalar_fields:
        if field not in state:
            continue
        value = state[field]
        if field in ("start_date", "end_date") and isinstance(value, str) and value:
            value = date.fromisoformat(value)
        setattr(entity, field, value)

    if kind.key == "holiday" and "date_text" in state:
        parsed = parse_holiday_date_text(state.get("date_text"))
        entity.date_text = parsed.date_text
        if "year" not in state:
            entity.year = parsed.year
        if "month" not in state:
            entity.month = parsed.month
        if "day" not in state:
            entity.day = parsed.day

    meta = dict(entity.extra_data or {})
    for field in METADATA_JSON_FIELDS:
        if field in state:
            meta[field] = state[field]
    entity.extra_data = meta


def metadata_snapshot_changed(kind: CatalogKind, before: dict, after: dict) -> bool:
    for key in kind.edit_keys:
        if before.get(key) != after.get(key):
            return True
    return False


async def find_by_name(
    db: AsyncSession,
    kind: CatalogKind,
    name: str,
    *,
    status: CatalogStatus | None = None,
) -> Any | None:
    normalized = name.strip()
    if not normalized:
        return None
    model = kind.model
    stmt = select(model).where(func.lower(model.name) == normalized.lower())
    if status is not None:
        stmt = stmt.where(model.status == status)
    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def create_pending(db: AsyncSession, kind: CatalogKind, name: str, **extra) -> Any:
    normalized = name.strip()
    slug_result = await db.execute(select(kind.model.slug))
    existing_slugs = {r[0] for r in slug_result.all()}
    slug = make_unique_slug(normalized, existing_slugs)
    entity = kind.model(
        name=normalized,
        slug=slug,
        status=CatalogStatus.PENDING,
        **extra,
    )
    db.add(entity)
    await db.flush()
    return entity


async def resolve_commercial_catalog(
    db: AsyncSession,
    editor: User,
    commercial: dict,
    kind: CatalogKind,
    *,
    comment: str | None = None,
) -> CatalogResolveResult:
    from app.services import EditService

    entity_id = commercial.get(kind.id_key)
    if entity_id:
        entity = await db.get(
            kind.model,
            UUID(entity_id) if isinstance(entity_id, str) else entity_id,
        )
        if not entity:
            raise ValueError(f"{kind.label} not found")
        if entity.status == CatalogStatus.REJECTED:
            raise ValueError(
                f"That {kind.label.lower()} was rejected — pick another or propose a new name"
            )
        updated = {**commercial, kind.id_key: str(entity.sbid)}
        updated.pop(kind.name_key, None)
        return CatalogResolveResult(commercial=updated)

    name = commercial.get(kind.name_key)
    if not name or not str(name).strip():
        return CatalogResolveResult(commercial=commercial)

    approved = await find_by_name(db, kind, str(name), status=CatalogStatus.APPROVED)
    if approved:
        updated = {**commercial, kind.id_key: str(approved.sbid)}
        updated.pop(kind.name_key, None)
        return CatalogResolveResult(commercial=updated)

    pending = await find_by_name(db, kind, str(name), status=CatalogStatus.PENDING)
    catalog_edit: Edit | None = None
    if not pending:
        pending = await create_pending(db, kind, str(name))
        catalog_edit = await EditService.create_edit(
            db,
            editor,
            kind.create_edit,
            kind.entity_type,
            after_state={"name": pending.name, kind.id_key: str(pending.sbid)},
            entity_id=pending.sbid,
            comment=(
                comment
                or f'New {kind.label.lower()} "{pending.name}" proposed with a video submission.'
            ),
            force_votable=True,
        )

    updated = {**commercial, kind.id_key: str(pending.sbid)}
    updated.pop(kind.name_key, None)
    return CatalogResolveResult(commercial=updated, catalog_edit=catalog_edit)


async def resolve_all_catalogs(
    db: AsyncSession,
    editor: User,
    commercial: dict,
) -> tuple[dict, list[Edit]]:
    edits: list[Edit] = []
    current = commercial
    for kind in ALL_CATALOG_KINDS:
        result = await resolve_commercial_catalog(db, editor, current, kind)
        current = result.commercial
        if result.catalog_edit:
            edits.append(result.catalog_edit)
    return current, edits


async def prepare_create_catalog_edit(db: AsyncSession, kind: CatalogKind, edit: Edit) -> None:
    state = dict(edit.after_state or {})
    if edit.entity_id:
        return

    entity_id = state.get(kind.id_key)
    if entity_id:
        edit.entity_id = UUID(entity_id) if isinstance(entity_id, str) else entity_id
        edit.after_state = state
        return

    name = (state.get("name") or "").strip()
    if not name:
        raise ValueError(f"{kind.label} name is required")

    approved = await find_by_name(db, kind, name, status=CatalogStatus.APPROVED)
    if approved:
        raise ValueError(f"An approved {kind.label.lower()} with that name already exists")

    pending = await find_by_name(db, kind, name, status=CatalogStatus.PENDING)
    if not pending:
        pending = await create_pending(db, kind, name)

    state[kind.id_key] = str(pending.sbid)
    state["name"] = pending.name
    edit.entity_id = pending.sbid
    edit.after_state = state


async def resolve_alias_links(
    db: AsyncSession,
    kind: CatalogKind,
    aliases: list[str] | None,
    *,
    exclude_sbid: UUID | None = None,
) -> list[dict]:
    links: list[dict] = []
    for alias in aliases or []:
        name = str(alias).strip()
        if not name:
            continue
        stmt = select(kind.model).where(
            func.lower(kind.model.name) == name.lower(),
            kind.model.status == CatalogStatus.APPROVED,
        )
        if exclude_sbid:
            stmt = stmt.where(kind.model.sbid != exclude_sbid)
        found = (await db.execute(stmt.limit(1))).scalar_one_or_none()
        links.append({"name": name, "sbid": str(found.sbid) if found else None})
    return links
