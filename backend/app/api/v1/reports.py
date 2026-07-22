"""User content reports for commercials and brands."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_mod, require_write_access
from app.database import get_db
from app.models import (
    Advertiser,
    Commercial,
    ContentReportReason,
    ContentReportStatus,
    User,
)
from app.schemas import (
    ContentReportPublic,
    ContentReportReview,
    ContentReportSubmit,
)
from app.services.commercial_reports import (
    count_open_reports,
    create_brand_report,
    create_commercial_report,
    list_open_reports,
    report_to_dict,
    review_content_report,
)

router = APIRouter(tags=["reports"])


async def _submit_report(
    db: AsyncSession,
    user: User,
    body: ContentReportSubmit,
    *,
    commercial: Commercial | None = None,
    advertiser: Advertiser | None = None,
) -> ContentReportPublic:
    try:
        reason = ContentReportReason(body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid report reason") from exc
    try:
        if commercial is not None:
            report = await create_commercial_report(
                db,
                commercial=commercial,
                reporter=user,
                reason=reason,
                details=body.details,
            )
        else:
            report = await create_brand_report(
                db,
                advertiser=advertiser,
                reporter=user,
                reason=reason,
                details=body.details,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(
        report, ["commercial", "advertiser", "reporter", "reviewed_by"]
    )
    return ContentReportPublic(**report_to_dict(report))


@router.post(
    "/commercials/{sbid}/report",
    response_model=ContentReportPublic,
    status_code=status.HTTP_201_CREATED,
)
async def report_commercial(
    sbid: UUID,
    body: ContentReportSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    commercial = await db.scalar(select(Commercial).where(Commercial.sbid == sbid))
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    return await _submit_report(db, user, body, commercial=commercial)


@router.post(
    "/advertisers/{sbid}/report",
    response_model=ContentReportPublic,
    status_code=status.HTTP_201_CREATED,
)
async def report_brand(
    sbid: UUID,
    body: ContentReportSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    advertiser = await db.scalar(select(Advertiser).where(Advertiser.sbid == sbid))
    if not advertiser:
        raise HTTPException(status_code=404, detail="Brand not found")
    return await _submit_report(db, user, body, advertiser=advertiser)


@router.get("/mod/content-reports", response_model=list[ContentReportPublic])
@router.get(
    "/mod/commercial-reports",
    response_model=list[ContentReportPublic],
    include_in_schema=False,
)
async def mod_list_content_reports(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    reports = await list_open_reports(db, offset=offset, limit=limit)
    return [ContentReportPublic(**report_to_dict(r)) for r in reports]


@router.get("/mod/content-reports/count")
async def mod_count_content_reports(
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    return {"count": await count_open_reports(db)}


@router.post(
    "/mod/content-reports/{report_id}/review",
    response_model=ContentReportPublic,
)
@router.post(
    "/mod/commercial-reports/{report_id}/review",
    response_model=ContentReportPublic,
    include_in_schema=False,
)
async def mod_review_content_report(
    report_id: UUID,
    body: ContentReportReview,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    try:
        new_status = ContentReportStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid status") from exc
    try:
        report = await review_content_report(
            db,
            report_id,
            mod,
            status=new_status,
            review_notes=body.review_notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return ContentReportPublic(**report_to_dict(report))
