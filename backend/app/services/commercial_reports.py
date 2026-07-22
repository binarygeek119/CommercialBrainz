"""User reports against commercials and brands."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Advertiser,
    Commercial,
    ContentReport,
    ContentReportReason,
    ContentReportStatus,
    User,
)

OPEN_STATUSES = (
    ContentReportStatus.PENDING,
    ContentReportStatus.UNDER_REVIEW,
)

REASON_OUTCOMES: dict[ContentReportReason, str] = {
    ContentReportReason.BANNED: "Needs to be flagged correctly",
    ContentReportReason.ADULT_AD: "Needs to be flagged correctly",
    ContentReportReason.ADULT_PORN: "Will be removed",
    ContentReportReason.HATE_SPEECH: "Moderators will review",
    ContentReportReason.OTHER: "Moderators will review",
}


async def create_content_report(
    db: AsyncSession,
    *,
    reporter: User,
    reason: ContentReportReason,
    details: str | None = None,
    commercial: Commercial | None = None,
    advertiser: Advertiser | None = None,
) -> ContentReport:
    if (commercial is None) == (advertiser is None):
        raise ValueError("Report must target exactly one of commercial or brand")

    cleaned = (details or "").strip() or None
    if reason == ContentReportReason.OTHER and not cleaned:
        raise ValueError("Please describe the issue for 'Other'")
    if cleaned and len(cleaned) > 2000:
        raise ValueError("Details must be 2000 characters or fewer")

    open_query = select(ContentReport.id).where(
        ContentReport.reporter_id == reporter.id,
        ContentReport.status.in_(OPEN_STATUSES),
    )
    if commercial is not None:
        open_query = open_query.where(ContentReport.commercial_id == commercial.sbid)
        target_label = "commercial"
    else:
        open_query = open_query.where(ContentReport.advertiser_id == advertiser.sbid)
        target_label = "brand"

    existing = await db.scalar(open_query)
    if existing:
        raise ValueError(f"You already have an open report for this {target_label}")

    report = ContentReport(
        commercial_id=commercial.sbid if commercial else None,
        advertiser_id=advertiser.sbid if advertiser else None,
        reporter_id=reporter.id,
        reason=reason,
        details=cleaned,
        status=ContentReportStatus.PENDING,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def create_commercial_report(
    db: AsyncSession,
    *,
    commercial: Commercial,
    reporter: User,
    reason: ContentReportReason,
    details: str | None = None,
) -> ContentReport:
    return await create_content_report(
        db,
        reporter=reporter,
        reason=reason,
        details=details,
        commercial=commercial,
    )


async def create_brand_report(
    db: AsyncSession,
    *,
    advertiser: Advertiser,
    reporter: User,
    reason: ContentReportReason,
    details: str | None = None,
) -> ContentReport:
    return await create_content_report(
        db,
        reporter=reporter,
        reason=reason,
        details=details,
        advertiser=advertiser,
    )


async def list_open_reports(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[ContentReport]:
    result = await db.execute(
        select(ContentReport)
        .options(
            selectinload(ContentReport.commercial),
            selectinload(ContentReport.advertiser),
            selectinload(ContentReport.reporter),
            selectinload(ContentReport.reviewed_by),
        )
        .where(ContentReport.status.in_(OPEN_STATUSES))
        .order_by(ContentReport.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_open_reports(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(ContentReport)
            .where(ContentReport.status.in_(OPEN_STATUSES))
        )
        or 0
    )


async def review_content_report(
    db: AsyncSession,
    report_id: UUID,
    mod: User,
    *,
    status: ContentReportStatus,
    review_notes: str | None = None,
) -> ContentReport:
    if status not in {
        ContentReportStatus.UNDER_REVIEW,
        ContentReportStatus.RESOLVED,
        ContentReportStatus.DISMISSED,
    }:
        raise ValueError("Invalid review status")

    result = await db.execute(
        select(ContentReport)
        .options(
            selectinload(ContentReport.commercial),
            selectinload(ContentReport.advertiser),
            selectinload(ContentReport.reporter),
            selectinload(ContentReport.reviewed_by),
        )
        .where(ContentReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise LookupError("Report not found")

    report.status = status
    report.review_notes = (review_notes or "").strip() or None
    report.reviewed_by_id = mod.id
    report.reviewed_at = datetime.now(UTC)
    report.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(report, ["reviewed_by"])
    return report


# Alias for earlier naming.
review_commercial_report = review_content_report


def report_to_dict(report: ContentReport) -> dict:
    if report.commercial_id:
        target_type = "commercial"
        target_title = report.commercial.title if report.commercial else None
    else:
        target_type = "brand"
        target_title = report.advertiser.name if report.advertiser else None
    return {
        "id": report.id,
        "target_type": target_type,
        "commercial_id": report.commercial_id,
        "advertiser_id": report.advertiser_id,
        "commercial_title": report.commercial.title if report.commercial else None,
        "advertiser_name": report.advertiser.name if report.advertiser else None,
        "target_title": target_title,
        "reporter_id": report.reporter_id,
        "reporter_username": report.reporter.username if report.reporter else None,
        "reason": report.reason.value,
        "details": report.details,
        "status": report.status.value,
        "review_notes": report.review_notes,
        "reviewed_by_id": report.reviewed_by_id,
        "reviewed_by_username": report.reviewed_by.username if report.reviewed_by else None,
        "reviewed_at": report.reviewed_at,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "outcome_hint": REASON_OUTCOMES.get(report.reason),
    }
