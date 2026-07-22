"""Browse shelves: filtered video queries and home sections."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Commercial,
    CommercialType,
    Edit,
    EditStatus,
    Video,
    VideoTag,
    VideoVisibility,
)
from app.services.edit_response import build_edit_public
from app.services.video_response import video_to_public_dict

BrowseSort = Literal["created_at", "updated_at"]

# Major US broadcast + kids networks for the "Channel commercials" shelf.
CHANNEL_COMMERCIAL_EXACT = frozenset(
    {
        "fox",
        "abc",
        "nbc",
        "cbs",
        "pbs",
        "nick",
        "cn",
        "disney",
        "nickelodeon",
        "cartoon network",
        "fox kids",
        "foxkids",
        "disney channel",
        "disney xd",
        "nicktoons",
        "boomerang",
        "pbs kids",
        "the cw",
        "cw",
    }
)

CHANNEL_COMMERCIAL_CONTAINS = (
    "nickelodeon",
    "cartoon network",
    "fox kids",
    "disney channel",
    "disney xd",
    "nicktoons",
    "boomerang",
    "pbs kids",
    "fox broadcasting",
)

CHANNEL_COMMERCIAL_CODES = ("fox", "abc", "nbc", "cbs", "pbs", "nick", "cn", "cw")


def bumper_channel_is_major_network(channel: str | None) -> bool:
    """True when a bumper_channel string matches major broadcasters / kids nets."""
    if not channel or not channel.strip():
        return False
    import re

    lowered = channel.strip().lower()
    if lowered in CHANNEL_COMMERCIAL_EXACT:
        return True
    for phrase in CHANNEL_COMMERCIAL_CONTAINS:
        if phrase in lowered:
            return True
    for code in CHANNEL_COMMERCIAL_CODES:
        if re.search(rf"(^|[^a-z0-9]){re.escape(code)}([^a-z0-9]|$)", lowered):
            return True
    return False


def enrich_browse_video(video: Video) -> dict[str, Any]:
    """Public video dict plus commercial fields used by browse shelves."""
    item = video_to_public_dict(video)
    commercial = video.commercial
    if commercial is not None:
        item["commercial_title"] = commercial.title
        item["commercial_type"] = (
            commercial.commercial_type.value if commercial.commercial_type else None
        )
        item["bumper_channel"] = commercial.bumper_channel
    else:
        item["commercial_title"] = None
        item["commercial_type"] = None
        item["bumper_channel"] = None
    return item


def channel_commercial_clause():
    """Bumpers whose bumper_channel matches major broadcasters / kids nets."""
    lowered = func.lower(func.trim(Commercial.bumper_channel))
    parts: list[Any] = [lowered.in_(CHANNEL_COMMERCIAL_EXACT)]
    for phrase in CHANNEL_COMMERCIAL_CONTAINS:
        parts.append(lowered.like(f"%{phrase}%"))
    for code in CHANNEL_COMMERCIAL_CODES:
        parts.append(
            Commercial.bumper_channel.op("~*")(rf"(^|[^[:alnum:]]){code}([^[:alnum:]]|$)")
        )
    return and_(
        Commercial.commercial_type == CommercialType.BUMPER,
        Commercial.bumper_channel.is_not(None),
        or_(*parts),
    )


def _base_video_stmt(*, load_commercial: bool = True):
    stmt = (
        select(Video)
        .join(Commercial, Video.commercial_id == Commercial.sbid)
        .where(Video.visibility == VideoVisibility.PUBLIC)
    )
    if load_commercial:
        stmt = stmt.options(selectinload(Video.commercial))
    return stmt


def _base_count_stmt():
    return (
        select(func.count())
        .select_from(Video)
        .join(Commercial, Video.commercial_id == Commercial.sbid)
        .where(Video.visibility == VideoVisibility.PUBLIC)
    )


def _apply_filters(
    stmt,
    *,
    advertiser: UUID | None = None,
    tag: str | None = None,
    commercial_type: CommercialType | None = None,
    channel_commercials: bool = False,
    updated_only: bool = False,
    main_only: bool = False,
):
    if advertiser is not None:
        stmt = stmt.where(Commercial.advertiser_id == advertiser)
    if tag:
        stmt = stmt.join(VideoTag, VideoTag.video_id == Video.sbid).where(
            VideoTag.tag == tag.lower()
        )
    if commercial_type is not None:
        stmt = stmt.where(Commercial.commercial_type == commercial_type)
    if channel_commercials:
        stmt = stmt.where(channel_commercial_clause())
    if updated_only:
        # Any ORM write after insert (metadata edits, fingerprints, popularity, …).
        stmt = stmt.where(Video.updated_at > Video.created_at)
    if main_only:
        stmt = stmt.where(
            or_(
                Commercial.main_video_id.is_(None),
                Video.sbid == Commercial.main_video_id,
            )
        )
    return stmt


def _order_clause(sort: BrowseSort, *, main_only: bool):
    primary = Video.created_at.desc() if sort == "created_at" else Video.updated_at.desc()
    if not main_only:
        return (primary, Video.sbid.desc())
    # Prefer main link, then popularity, then the shelf sort key.
    return (
        Commercial.sbid,
        case((Video.sbid == Commercial.main_video_id, 0), else_=1),
        Video.popularity_score.desc(),
        primary,
        Video.sbid.desc(),
    )


async def list_browse_videos(
    db: AsyncSession,
    *,
    advertiser: UUID | None = None,
    tag: str | None = None,
    commercial_type: CommercialType | None = None,
    channel_commercials: bool = False,
    sort: BrowseSort = "created_at",
    updated_only: bool = False,
    main_only: bool = False,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], int]:
    filter_kwargs = dict(
        advertiser=advertiser,
        tag=tag,
        commercial_type=commercial_type,
        channel_commercials=channel_commercials,
        updated_only=updated_only,
        main_only=False,
    )

    if main_only:
        count_stmt = select(func.count(func.distinct(Video.commercial_id))).select_from(
            Video
        ).join(Commercial, Video.commercial_id == Commercial.sbid).where(
            Video.visibility == VideoVisibility.PUBLIC
        )
        count_stmt = _apply_filters(count_stmt, **filter_kwargs)
        total = (await db.execute(count_stmt)).scalar() or 0

        order = _order_clause(sort, main_only=True)
        distinct_ids = (
            select(Video.sbid)
            .join(Commercial, Video.commercial_id == Commercial.sbid)
            .where(Video.visibility == VideoVisibility.PUBLIC)
        )
        distinct_ids = _apply_filters(distinct_ids, **filter_kwargs)
        distinct_ids = distinct_ids.order_by(*order).distinct(Commercial.sbid)
        id_rows = (await db.execute(distinct_ids.offset(offset).limit(limit))).all()
        video_ids = [row[0] for row in id_rows]
        if not video_ids:
            return [], total
        result = await db.execute(
            select(Video)
            .options(selectinload(Video.commercial))
            .where(Video.sbid.in_(video_ids))
        )
        by_id = {v.sbid: v for v in result.scalars().all()}
        videos = [by_id[i] for i in video_ids if i in by_id]
        return [enrich_browse_video(v) for v in videos], total

    stmt = _apply_filters(_base_video_stmt(), **filter_kwargs)
    count_stmt = _apply_filters(_base_count_stmt(), **filter_kwargs)
    total = (await db.execute(count_stmt)).scalar() or 0
    order = _order_clause(sort, main_only=False)
    result = await db.execute(stmt.order_by(*order).offset(offset).limit(limit))
    videos = list(result.scalars().all())
    return [enrich_browse_video(v) for v in videos], total


async def list_open_edits_for_browse(
    db: AsyncSession, *, offset: int = 0, limit: int = 16
) -> tuple[list[dict[str, Any]], int]:
    total = await db.scalar(
        select(func.count()).select_from(Edit).where(Edit.status == EditStatus.OPEN)
    )
    result = await db.execute(
        select(Edit)
        .options(selectinload(Edit.votes), selectinload(Edit.editor))
        .where(Edit.status == EditStatus.OPEN)
        .order_by(Edit.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items: list[dict[str, Any]] = []
    for edit in result.scalars().all():
        items.append((await build_edit_public(db, edit)).model_dump(mode="json"))
    return items, total or 0


SECTION_SPECS: list[dict[str, Any]] = [
    {
        "id": "needs_votes",
        "title": "Needs votes",
        "kind": "edits",
        "see_all_path": "/voting",
    },
    {
        "id": "newly_added",
        "title": "Newly added",
        "kind": "videos",
        "sort": "created_at",
        "main_only": False,
        "see_all_path": "/browse?section=newly_added",
    },
    {
        "id": "updated",
        "title": "Recently updated",
        "kind": "videos",
        "sort": "updated_at",
        "updated_only": True,
        "main_only": False,
        "see_all_path": "/browse?section=updated",
    },
    {
        "id": "psa",
        "title": "PSAs",
        "kind": "videos",
        "commercial_type": CommercialType.PSA,
        "main_only": True,
        "see_all_path": "/browse?section=psa",
    },
    {
        "id": "general_ad",
        "title": "General ads",
        "kind": "videos",
        "commercial_type": CommercialType.GENERAL_AD,
        "main_only": True,
        "see_all_path": "/browse?section=general_ad",
    },
    {
        "id": "service",
        "title": "Services",
        "kind": "videos",
        "commercial_type": CommercialType.SERVICE,
        "main_only": True,
        "see_all_path": "/browse?section=service",
    },
    {
        "id": "store",
        "title": "Stores",
        "kind": "videos",
        "commercial_type": CommercialType.STORE,
        "main_only": True,
        "see_all_path": "/browse?section=store",
    },
    {
        "id": "bumper",
        "title": "Bumpers",
        "kind": "videos",
        "commercial_type": CommercialType.BUMPER,
        "main_only": True,
        "see_all_path": "/browse?section=bumper",
    },
    {
        "id": "channel_commercial",
        "title": "Channel commercials",
        "kind": "videos",
        "channel_commercials": True,
        "main_only": True,
        "see_all_path": "/browse?section=channel_commercial",
    },
]


async def build_browse_home(db: AsyncSession, *, per_section: int = 16) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for spec in SECTION_SPECS:
        section: dict[str, Any] = {
            "id": spec["id"],
            "title": spec["title"],
            "kind": spec["kind"],
            "see_all_path": spec.get("see_all_path"),
            "items": [],
            "total": 0,
        }
        if spec["kind"] == "edits":
            items, total = await list_open_edits_for_browse(db, limit=per_section)
            section["items"] = items
            section["total"] = total
        else:
            items, total = await list_browse_videos(
                db,
                commercial_type=spec.get("commercial_type"),
                channel_commercials=bool(spec.get("channel_commercials")),
                sort=spec.get("sort", "created_at"),
                updated_only=bool(spec.get("updated_only")),
                main_only=bool(spec.get("main_only")),
                limit=per_section,
            )
            section["items"] = items
            section["total"] = total
        if section["total"] > 0 or section["id"] == "needs_votes":
            sections.append(section)
    return {"sections": sections}
