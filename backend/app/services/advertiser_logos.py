"""Brand logo gallery and popularity voting."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Advertiser,
    AdvertiserLogo,
    AdvertiserLogoVote,
    LogoPopularityChoice,
    User,
)


def logo_context_label(logo: AdvertiserLogo) -> str:
    parts: list[str] = []
    if logo.label:
        parts.append(logo.label)
    if logo.year is not None:
        date_part = str(logo.year)
        if logo.month is not None:
            date_part = f"{logo.year}-{logo.month:02d}"
        parts.append(date_part)
    if logo.event:
        parts.append(logo.event)
    return " · ".join(parts) if parts else "Logo version"


async def recompute_main_logo(db: AsyncSession, advertiser_id: UUID) -> None:
    advertiser = await db.get(Advertiser, advertiser_id)
    if not advertiser:
        return

    result = await db.execute(
        select(AdvertiserLogo)
        .where(AdvertiserLogo.advertiser_id == advertiser_id)
        .order_by(
            AdvertiserLogo.popularity_score.desc(),
            AdvertiserLogo.created_at.asc(),
        )
        .limit(1)
    )
    top = result.scalar_one_or_none()
    if top:
        advertiser.main_logo_id = top.id
        advertiser.logo_url = top.image_url
    else:
        advertiser.main_logo_id = None
        advertiser.logo_url = None


async def refresh_logo_popularity(db: AsyncSession, logo_id: UUID) -> int:
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (AdvertiserLogoVote.choice == LogoPopularityChoice.UP, 1),
                        else_=-1,
                    )
                ),
                0,
            )
        ).where(AdvertiserLogoVote.logo_id == logo_id)
    )
    score = int(result.scalar() or 0)
    logo = await db.get(AdvertiserLogo, logo_id)
    if logo:
        logo.popularity_score = score
        await recompute_main_logo(db, logo.advertiser_id)
    return score


async def cast_logo_popularity_vote(
    db: AsyncSession,
    logo: AdvertiserLogo,
    voter: User,
    choice: LogoPopularityChoice | None,
) -> AdvertiserLogoVote | None:
    existing = await db.execute(
        select(AdvertiserLogoVote).where(
            AdvertiserLogoVote.logo_id == logo.id,
            AdvertiserLogoVote.voter_id == voter.id,
        )
    )
    vote = existing.scalar_one_or_none()

    if choice is None:
        if vote:
            await db.delete(vote)
            await db.flush()
            await refresh_logo_popularity(db, logo.id)
        return None

    if vote:
        if vote.choice == choice:
            return vote
        vote.choice = choice
    else:
        vote = AdvertiserLogoVote(logo_id=logo.id, voter_id=voter.id, choice=choice)
        db.add(vote)

    await db.flush()
    await refresh_logo_popularity(db, logo.id)
    return vote


async def list_advertiser_logos(
    db: AsyncSession,
    advertiser_id: UUID,
    *,
    viewer: User | None = None,
) -> list[dict]:
    result = await db.execute(
        select(AdvertiserLogo)
        .where(AdvertiserLogo.advertiser_id == advertiser_id)
        .order_by(
            AdvertiserLogo.popularity_score.desc(),
            AdvertiserLogo.year.desc().nullslast(),
            AdvertiserLogo.month.desc().nullslast(),
            AdvertiserLogo.created_at.desc(),
        )
    )
    logos = result.scalars().all()
    if not logos:
        return []

    viewer_votes: dict[UUID, LogoPopularityChoice] = {}
    if viewer:
        vote_result = await db.execute(
            select(AdvertiserLogoVote).where(
                AdvertiserLogoVote.logo_id.in_([logo.id for logo in logos]),
                AdvertiserLogoVote.voter_id == viewer.id,
            )
        )
        viewer_votes = {v.logo_id: v.choice for v in vote_result.scalars().all()}

    advertiser = await db.get(Advertiser, advertiser_id)
    main_id = advertiser.main_logo_id if advertiser else None

    return [
        {
            "id": logo.id,
            "advertiser_id": logo.advertiser_id,
            "image_url": logo.image_url,
            "label": logo.label,
            "year": logo.year,
            "month": logo.month,
            "event": logo.event,
            "notes": logo.notes,
            "popularity_score": logo.popularity_score,
            "is_main": logo.id == main_id,
            "context_label": logo_context_label(logo),
            "created_at": logo.created_at,
            "viewer_vote": viewer_votes.get(logo.id).value if logo.id in viewer_votes else None,
        }
        for logo in logos
    ]


async def create_logo_from_edit(
    db: AsyncSession,
    *,
    advertiser_id: UUID,
    image_url: str,
    editor_id: UUID,
    edit_id: UUID,
    label: str | None = None,
    year: int | None = None,
    month: int | None = None,
    event: str | None = None,
    notes: str | None = None,
) -> AdvertiserLogo:
    logo = AdvertiserLogo(
        advertiser_id=advertiser_id,
        image_url=image_url,
        label=label,
        year=year,
        month=month,
        event=event,
        notes=notes,
        submitted_by=editor_id,
        edit_id=edit_id,
        popularity_score=0,
    )
    db.add(logo)
    await db.flush()
    return logo


async def get_logo_for_advertiser(
    db: AsyncSession, advertiser_id: UUID, logo_id: UUID
) -> AdvertiserLogo | None:
    result = await db.execute(
        select(AdvertiserLogo)
        .options(selectinload(AdvertiserLogo.advertiser))
        .where(
            AdvertiserLogo.id == logo_id,
            AdvertiserLogo.advertiser_id == advertiser_id,
        )
    )
    return result.scalar_one_or_none()
