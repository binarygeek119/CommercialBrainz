"""User commercial content reports."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_mod, require_write_access
from app.database import get_db
from app.models import (
    Commercial,
    CommercialReportReason,
    CommercialReportStatus,
    User,
)
from app.schemas import (
    CommercialReportPublic,
    CommercialReportReview,
    CommercialReportSubmit,
)
from app.services.commercial_reports import (
    count_open_reports,
    create_commercial_report,
    list_open_reports,
    report_to_dict,
    review_commercial_report,
)

router = APIRouter(tags=["reports"])


@router.post(
    "/commercials/{sbid}/report",
    response_model=CommercialReportPublic,
    status_code=status.HTTP_201_CREATED,
)
async def report_commercial(
    sbid: UUID,
    body: CommercialReportSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_write_access),
):
    commercial = await db.scalar(select(Commercial).where(Commercial.sbid == sbid))
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial not found")
    try:
        reason = CommercialReportReason(body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid report reason") from exc
    try:
        report = await create_commercial_report(
            db,
            commercial=commercial,
            reporter=user,
            reason=reason,
            details=body.details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(report, ["commercial", "reporter", "reviewed_by"])
    return CommercialReportPublic(**report_to_dict(report))


@router.get("/mod/commercial-reports", response_model=list[CommercialReportPublic])
async def mod_list_commercial_reports(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    reports = await list_open_reports(db, offset=offset, limit=limit)
    return [CommercialReportPublic(**report_to_dict(r)) for r in reports]


@router.get("/mod/commercial-reports/count")
async def mod_count_commercial_reports(
    db: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_mod),
):
    return {"count": await count_open_reports(db)}


@router.post(
    "/mod/commercial-reports/{report_id}/review",
    response_model=CommercialReportPublic,
)
async def mod_review_commercial_report(
    report_id: UUID,
    body: CommercialReportReview,
    db: AsyncSession = Depends(get_db),
    mod: User = Depends(require_mod),
):
    try:
        new_status = CommercialReportStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid status") from exc
    try:
        report = await review_commercial_report(
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
    return CommercialReportPublic(**report_to_dict(report))
