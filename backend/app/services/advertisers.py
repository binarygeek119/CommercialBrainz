"""Advertiser lookup, pending brands, and approval edits."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Advertiser, AdvertiserStatus, Edit, EditType, User
from app.utils import make_unique_slug


@dataclass
class CommercialAdvertiserResult:
    commercial: dict
    brand_edit: Edit | None = None


async def find_advertiser_by_name(
    db: AsyncSession,
    name: str,
    *,
    status: AdvertiserStatus | None = None,
) -> Advertiser | None:
    normalized = name.strip()
    if not normalized:
        return None
    stmt = select(Advertiser).where(func.lower(Advertiser.name) == normalized.lower())
    if status is not None:
        stmt = stmt.where(Advertiser.status == status)
    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def find_approved_advertiser_by_name(db: AsyncSession, name: str) -> Advertiser | None:
    return await find_advertiser_by_name(db, name, status=AdvertiserStatus.APPROVED)


async def create_pending_advertiser(db: AsyncSession, name: str) -> Advertiser:
    normalized = name.strip()
    slug_result = await db.execute(select(Advertiser.slug))
    existing_slugs = {r[0] for r in slug_result.all()}
    slug = make_unique_slug(normalized, existing_slugs)
    advertiser = Advertiser(
        name=normalized,
        slug=slug,
        status=AdvertiserStatus.PENDING,
    )
    db.add(advertiser)
    await db.flush()
    return advertiser


async def resolve_commercial_advertiser(
    db: AsyncSession,
    editor: User,
    commercial: dict,
    *,
    brand_comment: str | None = None,
) -> CommercialAdvertiserResult:
    """Resolve advertiser for a video submission; queue a brand edit when creating new."""
    from app.services import EditService

    advertiser_id = commercial.get("advertiser_id")
    if advertiser_id:
        adv = await db.get(
            Advertiser, UUID(advertiser_id) if isinstance(advertiser_id, str) else advertiser_id
        )
        if not adv:
            raise ValueError("Advertiser not found")
        if adv.status == AdvertiserStatus.REJECTED:
            raise ValueError("That brand was rejected — pick another or propose a new name")
        updated = {**commercial, "advertiser_id": str(adv.sbid)}
        updated.pop("advertiser_name", None)
        return CommercialAdvertiserResult(commercial=updated)

    name = commercial.get("advertiser_name")
    if not name or not str(name).strip():
        return CommercialAdvertiserResult(commercial=commercial)

    approved = await find_approved_advertiser_by_name(db, str(name))
    if approved:
        updated = {**commercial, "advertiser_id": str(approved.sbid)}
        updated.pop("advertiser_name", None)
        return CommercialAdvertiserResult(commercial=updated)

    pending = await find_advertiser_by_name(db, str(name), status=AdvertiserStatus.PENDING)
    brand_edit: Edit | None = None
    if not pending:
        pending = await create_pending_advertiser(db, str(name))
        brand_edit = await EditService.create_edit(
            db,
            editor,
            EditType.CREATE_ADVERTISER,
            "advertiser",
            after_state={"name": pending.name, "advertiser_id": str(pending.sbid)},
            entity_id=pending.sbid,
            comment=brand_comment or f'New brand "{pending.name}" proposed with a video submission.',
            force_votable=True,
        )

    updated = {**commercial, "advertiser_id": str(pending.sbid)}
    updated.pop("advertiser_name", None)
    return CommercialAdvertiserResult(commercial=updated, brand_edit=brand_edit)


async def prepare_create_advertiser_edit(db: AsyncSession, edit) -> None:
    """Bind a create_advertiser edit to a pending advertiser row."""
    state = dict(edit.after_state or {})
    if edit.entity_id:
        return

    advertiser_id = state.get("advertiser_id")
    if advertiser_id:
        edit.entity_id = UUID(advertiser_id) if isinstance(advertiser_id, str) else advertiser_id
        edit.after_state = state
        return

    name = (state.get("name") or "").strip()
    if not name:
        raise ValueError("Brand name is required")

    approved = await find_approved_advertiser_by_name(db, name)
    if approved:
        raise ValueError("An approved brand with that name already exists")

    pending = await find_advertiser_by_name(db, name, status=AdvertiserStatus.PENDING)
    if not pending:
        pending = await create_pending_advertiser(db, name)

    state["advertiser_id"] = str(pending.sbid)
    state["name"] = pending.name
    edit.entity_id = pending.sbid
    edit.after_state = state
