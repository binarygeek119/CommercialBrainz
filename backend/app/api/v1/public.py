from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user_optional
from app.database import get_db
from app.models import (
    Advertiser,
    AdvertiserStatus,
    Commercial,
    Edit,
    User,
    Video,
    VideoTag,
    VideoVisibility,
)
from app.schemas import (
    AdvertiserDetail,
    AdvertiserPublic,
    AgencyPublic,
    BrandAliasLink,
    CommercialDetail,
    CommercialListItem,
    CommercialPublic,
    PaginatedResponse,
    SearchResult,
    UserEditSummary,
    UserProfilePublic,
    VideoDetail,
    VideoPublic,
)
from app.services import SearchService
from app.services.advertiser_metadata import advertiser_public_dict, resolve_alias_links
from app.services.bulk_import_marker import (
    commercial_was_bulk_imported_for_viewer,
    filter_tags_for_viewer,
)
from app.services.rate_limit import check_rate_limit, compute_etag
from app.services.user_profile import edit_summary_title
from app.services.video_response import (
    commercial_list_thumbnail_url,
    list_commercial_videos_public,
    video_to_public,
)

router = APIRouter(tags=["public"])


def _video_public(v: Video) -> VideoPublic:
    return video_to_public(v)


@router.get("/videos/{sbid}", response_model=VideoDetail)
async def get_video(
    sbid: UUID,
    request: Request,
    response: Response,
    if_none_match: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    video = await SearchService.get_video_detail(db, sbid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    detail = VideoDetail(
        **_video_public(video).model_dump(),
        commercial=(
            CommercialPublic(
                **{
                    **CommercialPublic.model_validate(video.commercial).model_dump(),
                    "was_bulk_imported": commercial_was_bulk_imported_for_viewer(
                        video.commercial, user
                    ),
                }
            )
            if video.commercial
            else None
        ),
        advertiser=AdvertiserPublic(**advertiser_public_dict(video.commercial.advertiser))
        if video.commercial and video.commercial.advertiser
        else None,
        agency=AgencyPublic.model_validate(video.commercial.agency)
        if video.commercial and video.commercial.agency
        else None,
        credits=[{"role": c.role, "name": c.name} for c in video.credits],
        tags=filter_tags_for_viewer([t.tag for t in video.tags], user),
    )
    etag = compute_etag(detail.model_dump(mode="json"))
    if if_none_match == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    return detail


def _commercial_list_item(commercial: Commercial, viewer: User | None = None) -> CommercialListItem:
    public_videos = [v for v in commercial.videos if v.visibility == VideoVisibility.PUBLIC]
    base = CommercialPublic.model_validate(commercial).model_dump()
    base["was_bulk_imported"] = commercial_was_bulk_imported_for_viewer(commercial, viewer)
    return CommercialListItem(
        **base,
        advertiser_name=commercial.advertiser.name if commercial.advertiser else None,
        public_video_count=len(public_videos),
        thumbnail_url=commercial_list_thumbnail_url(commercial),
    )


@router.get("/commercials", response_model=PaginatedResponse)
async def list_commercials(
    request: Request,
    q: str = Query(default="", max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """List commercials for browsing (searchable)."""
    await check_rate_limit(request, user is not None)
    stmt = select(Commercial).options(
        selectinload(Commercial.advertiser),
        selectinload(Commercial.videos),
    )
    count_stmt = select(func.count()).select_from(Commercial)
    if q.strip():
        pattern = f"%{q.strip()}%"
        title_filter = or_(
            Commercial.title.ilike(pattern),
            Commercial.campaign_name.ilike(pattern),
            Commercial.description.ilike(pattern),
        )
        stmt = stmt.where(title_filter)
        count_stmt = count_stmt.where(title_filter)
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.order_by(Commercial.title).offset(offset).limit(limit))
    items = [_commercial_list_item(c, user).model_dump() for c in result.scalars().all()]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/commercials/{sbid}", response_model=CommercialDetail)
async def get_commercial(
    sbid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    result = await db.execute(
        select(Commercial)
        .options(
            selectinload(Commercial.advertiser),
            selectinload(Commercial.store),
            selectinload(Commercial.service),
            selectinload(Commercial.event),
            selectinload(Commercial.holiday),
            selectinload(Commercial.agency),
            selectinload(Commercial.videos),
            selectinload(Commercial.products),
        )
        .where(Commercial.sbid == sbid)
    )
    commercial = result.scalar_one_or_none()
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")


    videos = await list_commercial_videos_public(db, commercial, viewer=user)
    commercial_public = CommercialPublic.model_validate(commercial).model_dump()
    commercial_public["was_bulk_imported"] = commercial_was_bulk_imported_for_viewer(
        commercial, user
    )
    from app.services.catalog import ALL_CATALOG_KINDS, entity_public_dict

    catalog_embeds = {}
    for kind in ALL_CATALOG_KINDS:
        related = getattr(commercial, kind.key, None)
        catalog_embeds[kind.key] = entity_public_dict(kind, related) if related else None
    return CommercialDetail(
        **commercial_public,
        advertiser=AdvertiserPublic(**advertiser_public_dict(commercial.advertiser))
        if commercial.advertiser
        else None,
        store=catalog_embeds["store"],
        service=catalog_embeds["service"],
        event=catalog_embeds["event"],
        holiday=catalog_embeds["holiday"],
        agency=AgencyPublic.model_validate(commercial.agency) if commercial.agency else None,
        videos=videos,
        products=[p.name for p in commercial.products],
    )


@router.get("/advertisers", response_model=PaginatedResponse)
async def list_advertisers(
    request: Request,
    q: str = Query(default="", max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """List advertisers/brands for submission metadata (searchable)."""
    await check_rate_limit(request, user is not None)
    stmt = select(Advertiser).where(Advertiser.status == AdvertiserStatus.APPROVED)
    count_stmt = select(func.count()).select_from(Advertiser).where(
        Advertiser.status == AdvertiserStatus.APPROVED
    )
    if q.strip():
        pattern = f"%{q.strip()}%"
        alias_match = func.coalesce(Advertiser.extra_data["aliases"].astext, "").ilike(pattern)
        stmt = stmt.where(or_(Advertiser.name.ilike(pattern), alias_match))
        count_stmt = count_stmt.where(or_(Advertiser.name.ilike(pattern), alias_match))
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(Advertiser.name).offset(offset).limit(limit)
    )
    items = [
        AdvertiserPublic(**advertiser_public_dict(a)).model_dump()
        for a in result.scalars().all()
    ]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/advertisers/{sbid}", response_model=AdvertiserDetail)
async def get_advertiser(
    sbid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    result = await db.execute(
        select(Advertiser)
        .options(selectinload(Advertiser.commercials))
        .where(Advertiser.sbid == sbid)
    )
    advertiser = result.scalar_one_or_none()
    if not advertiser or advertiser.status != AdvertiserStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Advertiser not found")

    aliases = (advertiser.extra_data or {}).get("aliases") or []
    alias_links = await resolve_alias_links(db, aliases, exclude_sbid=advertiser.sbid)

    return AdvertiserDetail(
        **AdvertiserPublic(**advertiser_public_dict(advertiser)).model_dump(),
        commercials=[CommercialPublic.model_validate(c) for c in advertiser.commercials],
        alias_links=[BrandAliasLink(**link) for link in alias_links],
    )


@router.get("/users/{username}", response_model=UserProfilePublic)
async def get_user_profile(
    username: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    profile_user = await db.scalar(
        select(User).where(User.username == username, User.is_active.is_(True))
    )
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    submission_count = (
        await db.scalar(
            select(func.count())
            .select_from(Edit)
            .where(Edit.editor_id == profile_user.id)
        )
        or 0
    )
    return UserProfilePublic(
        id=profile_user.id,
        username=profile_user.username,
        role=profile_user.role.value,
        reputation_points=float(profile_user.reputation_points),
        accepted_edits_count=profile_user.accepted_edits_count,
        submission_count=submission_count,
        is_power_user=bool(profile_user.bulk_submit_enabled),
        created_at=profile_user.created_at,
    )


@router.get("/users/{username}/edits", response_model=PaginatedResponse)
async def list_user_edits(
    username: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    profile_user = await db.scalar(
        select(User).where(User.username == username, User.is_active.is_(True))
    )
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    base_filter = Edit.editor_id == profile_user.id
    total = await db.scalar(select(func.count()).select_from(Edit).where(base_filter)) or 0
    result = await db.execute(
        select(Edit)
        .options(selectinload(Edit.votes))
        .where(base_filter)
        .order_by(Edit.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = [
        UserEditSummary(
            id=edit.id,
            edit_type=edit.edit_type.value,
            status=edit.status.value,
            title=edit_summary_title(edit),
            entity_type=edit.entity_type,
            entity_id=edit.entity_id,
            comment=edit.comment,
            created_at=edit.created_at,
            closed_at=edit.closed_at,
            vote_count=len(edit.votes),
        ).model_dump()
        for edit in result.scalars().all()
    ]
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/search", response_model=list[SearchResult])
async def search(
    request: Request,
    query: str = Query(min_length=1),
    type: str = Query(default="video"),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    results = await SearchService.search(db, query, type, limit)
    return [SearchResult(**r) for r in results]


@router.get("/browse/videos", response_model=PaginatedResponse)
async def browse_videos(
    request: Request,
    advertiser: UUID | None = None,
    tag: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    stmt = (
        select(Video)
        .join(Commercial, Video.commercial_id == Commercial.sbid)
        .where(Video.visibility == VideoVisibility.PUBLIC)
    )
    count_stmt = (
        select(func.count())
        .select_from(Video)
        .join(Commercial, Video.commercial_id == Commercial.sbid)
        .where(Video.visibility == VideoVisibility.PUBLIC)
    )

    if advertiser:
        stmt = stmt.where(Commercial.advertiser_id == advertiser)
        count_stmt = count_stmt.where(Commercial.advertiser_id == advertiser)
    if tag:
        stmt = stmt.join(VideoTag, VideoTag.video_id == Video.sbid).where(
            VideoTag.tag == tag.lower()
        )
        count_stmt = count_stmt.join(VideoTag, VideoTag.video_id == Video.sbid).where(
            VideoTag.tag == tag.lower()
        )

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.order_by(Video.created_at.desc()).offset(offset).limit(limit))
    videos = result.scalars().all()
    return PaginatedResponse(
        items=[_video_public(v).model_dump() for v in videos],
        total=total,
        offset=offset,
        limit=limit,
    )
