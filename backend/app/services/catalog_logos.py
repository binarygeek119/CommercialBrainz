"""Catalog logo gallery helpers (Store / Service / Event / Holiday)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LogoPopularityChoice, User
from app.services.catalog import CatalogKind


def logo_event_value(logo) -> str | None:
    if hasattr(logo, "event_label"):
        return logo.event_label
    return getattr(logo, "event", None)


def set_logo_event(logo, value: str | None) -> None:
    if hasattr(logo, "event_label"):
        logo.event_label = value
    else:
        logo.event = value


def logo_context_label(logo) -> str:
    parts: list[str] = []
    if logo.label:
        parts.append(logo.label)
    if logo.year is not None:
        date_part = str(logo.year)
        if logo.month is not None:
            date_part = f"{logo.year}-{logo.month:02d}"
        parts.append(date_part)
    event = logo_event_value(logo)
    if event:
        parts.append(event)
    return " · ".join(parts) if parts else "Logo version"


async def recompute_main_logo(db: AsyncSession, kind: CatalogKind, entity_id: UUID) -> None:
    entity = await db.get(kind.model, entity_id)
    if not entity:
        return

    parent_col = getattr(kind.logo_model, kind.parent_fk)
    result = await db.execute(
        select(kind.logo_model)
        .where(parent_col == entity_id)
        .order_by(
            kind.logo_model.popularity_score.desc(),
            kind.logo_model.created_at.asc(),
        )
        .limit(1)
    )
    top = result.scalar_one_or_none()
    if top:
        entity.main_logo_id = top.id
        entity.logo_url = top.image_url
    else:
        entity.main_logo_id = None
        entity.logo_url = None


async def refresh_logo_popularity(db: AsyncSession, kind: CatalogKind, logo_id: UUID) -> int:
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (kind.vote_model.choice == LogoPopularityChoice.UP, 1),
                        else_=-1,
                    )
                ),
                0,
            )
        ).where(kind.vote_model.logo_id == logo_id)
    )
    score = int(result.scalar() or 0)
    logo = await db.get(kind.logo_model, logo_id)
    if logo:
        logo.popularity_score = score
        parent_id = getattr(logo, kind.parent_fk)
        await recompute_main_logo(db, kind, parent_id)
    return score


async def cast_logo_popularity_vote(
    db: AsyncSession,
    kind: CatalogKind,
    logo,
    voter: User,
    choice: LogoPopularityChoice | None,
):
    existing = await db.execute(
        select(kind.vote_model).where(
            kind.vote_model.logo_id == logo.id,
            kind.vote_model.voter_id == voter.id,
        )
    )
    vote = existing.scalar_one_or_none()

    if choice is None:
        if vote:
            await db.delete(vote)
            await db.flush()
            await refresh_logo_popularity(db, kind, logo.id)
        return None

    if vote:
        if vote.choice == choice:
            return vote
        vote.choice = choice
    else:
        vote = kind.vote_model(logo_id=logo.id, voter_id=voter.id, choice=choice)
        db.add(vote)

    await db.flush()
    await refresh_logo_popularity(db, kind, logo.id)
    return vote


async def list_logos(
    db: AsyncSession,
    kind: CatalogKind,
    entity_id: UUID,
    *,
    viewer: User | None = None,
) -> list[dict]:
    parent_col = getattr(kind.logo_model, kind.parent_fk)
    result = await db.execute(
        select(kind.logo_model)
        .where(parent_col == entity_id)
        .order_by(
            kind.logo_model.popularity_score.desc(),
            kind.logo_model.year.desc().nullslast(),
            kind.logo_model.month.desc().nullslast(),
            kind.logo_model.created_at.desc(),
        )
    )
    logos = result.scalars().all()
    if not logos:
        return []

    viewer_votes: dict[UUID, LogoPopularityChoice] = {}
    if viewer:
        vote_result = await db.execute(
            select(kind.vote_model).where(
                kind.vote_model.logo_id.in_([logo.id for logo in logos]),
                kind.vote_model.voter_id == viewer.id,
            )
        )
        viewer_votes = {v.logo_id: v.choice for v in vote_result.scalars().all()}

    entity = await db.get(kind.model, entity_id)
    main_id = entity.main_logo_id if entity else None

    rows = []
    for logo in logos:
        rows.append(
            {
                "id": logo.id,
                kind.parent_fk: getattr(logo, kind.parent_fk),
                "image_url": logo.image_url,
                "label": logo.label,
                "year": logo.year,
                "month": logo.month,
                "event": logo_event_value(logo),
                "notes": logo.notes,
                "popularity_score": logo.popularity_score,
                "is_main": logo.id == main_id,
                "context_label": logo_context_label(logo),
                "created_at": logo.created_at,
                "viewer_vote": viewer_votes.get(logo.id).value
                if logo.id in viewer_votes
                else None,
            }
        )
    return rows


async def create_logo_from_edit(
    db: AsyncSession,
    kind: CatalogKind,
    *,
    entity_id: UUID,
    image_url: str,
    editor_id: UUID,
    edit_id: UUID,
    label: str | None = None,
    year: int | None = None,
    month: int | None = None,
    event: str | None = None,
    notes: str | None = None,
):
    kwargs = {
        kind.parent_fk: entity_id,
        "image_url": image_url,
        "label": label,
        "year": year,
        "month": month,
        "notes": notes,
        "submitted_by": editor_id,
        "edit_id": edit_id,
        "popularity_score": 0,
    }
    logo = kind.logo_model(**kwargs)
    set_logo_event(logo, event)
    db.add(logo)
    await db.flush()
    return logo


async def get_logo_for_entity(
    db: AsyncSession, kind: CatalogKind, entity_id: UUID, logo_id: UUID
):
    parent_col = getattr(kind.logo_model, kind.parent_fk)
    result = await db.execute(
        select(kind.logo_model).where(
            kind.logo_model.id == logo_id,
            parent_col == entity_id,
        )
    )
    return result.scalar_one_or_none()
