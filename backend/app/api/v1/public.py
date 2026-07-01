from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user_optional
from app.database import get_db
from app.models import (
    Advertiser,
    Agency,
    Commercial,
    CommercialProduct,
    User,
    Video,
    VideoCredit,
    VideoTag,
    VideoVisibility,
)
from app.schemas import (
    AdvertiserDetail,
    AdvertiserPublic,
    CommercialDetail,
    CommercialPublic,
    PaginatedResponse,
    SearchResult,
    VideoDetail,
    VideoPublic,
)
from app.services import SearchService
from app.services.rate_limit import check_rate_limit, compute_etag
from app.utils import extract_youtube_id

router = APIRouter(tags=["public"])


def _video_public(v: Video) -> VideoPublic:
    data = {
        "sbid": v.sbid,
        "commercial_id": v.commercial_id,
        "youtube_id": v.youtube_id if v.visibility == VideoVisibility.PUBLIC else None,
        "youtube_url": v.youtube_url if v.visibility == VideoVisibility.PUBLIC else None,
        "channel_name": v.channel_name,
        "upload_date": v.upload_date.isoformat() if v.upload_date else None,
        "duration_ms": v.duration_ms,
        "aspect_ratio": v.aspect_ratio,
        "resolution": v.resolution,
        "language": v.language,
        "region": v.region,
        "market": v.market,
        "first_aired_date": v.first_aired_date.isoformat() if v.first_aired_date else None,
        "last_aired_date": v.last_aired_date.isoformat() if v.last_aired_date else None,
        "network": v.network,
        "transcript": v.transcript,
        "slogan": v.slogan,
        "cta_text": v.cta_text,
        "metadata": v.metadata,
        "visibility": v.visibility.value,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }
    return VideoPublic(**data)


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
        commercial=CommercialPublic.model_validate(video.commercial) if video.commercial else None,
        advertiser=AdvertiserPublic.model_validate(video.commercial.advertiser)
        if video.commercial and video.commercial.advertiser
        else None,
        agency=AgencyPublic.model_validate(video.commercial.agency)
        if video.commercial and video.commercial.agency
        else None,
        credits=[{"role": c.role, "name": c.name} for c in video.credits],
        tags=[t.tag for t in video.tags],
    )
    etag = compute_etag(detail.model_dump(mode="json"))
    if if_none_match == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    return detail


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
            selectinload(Commercial.agency),
            selectinload(Commercial.videos),
            selectinload(Commercial.products),
        )
        .where(Commercial.sbid == sbid)
    )
    commercial = result.scalar_one_or_none()
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")

    public_videos = [v for v in commercial.videos if v.visibility == VideoVisibility.PUBLIC]
    return CommercialDetail(
        **CommercialPublic.model_validate(commercial).model_dump(),
        advertiser=AdvertiserPublic.model_validate(commercial.advertiser) if commercial.advertiser else None,
        agency=AgencyPublic.model_validate(commercial.agency) if commercial.agency else None,
        videos=[_video_public(v) for v in public_videos],
        products=[p.name for p in commercial.products],
    )


@router.get("/advertisers/{sbid}", response_model=AdvertiserDetail)
async def get_advertiser(
    sbid: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    await check_rate_limit(request, user is not None)
    result = await db.execute(
        select(Advertiser).options(selectinload(Advertiser.commercials)).where(Advertiser.sbid == sbid)
    )
    advertiser = result.scalar_one_or_none()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    return AdvertiserDetail(
        **AdvertiserPublic.model_validate(advertiser).model_dump(),
        commercials=[CommercialPublic.model_validate(c) for c in advertiser.commercials],
    )


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
        stmt = stmt.join(VideoTag, VideoTag.video_id == Video.sbid).where(VideoTag.tag == tag.lower())
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
