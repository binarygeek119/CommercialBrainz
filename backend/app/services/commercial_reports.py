"""User reports against commercials."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Commercial,
    CommercialReport,
    CommercialReportReason,
    CommercialReportStatus,
    User,
)

OPEN_STATUSES = (
    CommercialReportStatus.PENDING,
    CommercialReportStatus.UNDER_REVIEW,
)

REASON_OUTCOMES: dict[CommercialReportReason, str] = {
    CommercialReportReason.BANNED: "Needs to be flagged correctly",
    CommercialReportReason.ADULT_AD: "Needs to be flagged correctly",
    CommercialReportReason.ADULT_PORN: "Will be removed",
    CommercialReportReason.HATE_SPEECH: "Moderators will review",
    CommercialReportReason.OTHER: "Moderators will review",
}


async def create_commercial_report(
    db: AsyncSession,
    *,
    commercial: Commercial,
    reporter: User,
    reason: CommercialReportReason,
    details: str | None = None,
) -> CommercialReport:
    existing = await db.scalar(
        select(CommercialReport.id).where(
            CommercialReport.commercial_id == commercial.sbid,
            CommercialReport.reporter_id == reporter.id,
            CommercialReport.status.in_(OPEN_STATUSES),
        )
    )
    if existing:
        raise ValueError("You already have an open report for this commercial")

    cleaned = (details or "").strip() or None
    if reason == CommercialReportReason.OTHER and not cleaned:
        raise ValueError("Please describe the issue for 'Other'")
    if cleaned and len(cleaned) > 2000:
        raise ValueError("Details must be 2000 characters or fewer")

    report = CommercialReport(
        commercial_id=commercial.sbid,
        reporter_id=reporter.id,
        reason=reason,
        details=cleaned,
        status=CommercialReportStatus.PENDING,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def list_open_reports(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[CommercialReport]:
    result = await db.execute(
        select(CommercialReport)
        .options(
            selectinload(CommercialReport.commercial),
            selectinload(CommercialReport.reporter),
            selectinload(CommercialReport.reviewed_by),
        )
        .where(CommercialReport.status.in_(OPEN_STATUSES))
        .order_by(CommercialReport.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_open_reports(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(CommercialReport)
            .where(CommercialReport.status.in_(OPEN_STATUSES))
        )
        or 0
    )


async def review_commercial_report(
    db: AsyncSession,
    report_id: UUID,
    mod: User,
    *,
    status: CommercialReportStatus,
    review_notes: str | None = None,
) -> CommercialReport:
    if status not in {
        CommercialReportStatus.UNDER_REVIEW,
        CommercialReportStatus.RESOLVED,
        CommercialReportStatus.DISMISSED,
    }:
        raise ValueError("Invalid review status")

    result = await db.execute(
        select(CommercialReport)
        .options(
            selectinload(CommercialReport.commercial),
            selectinload(CommercialReport.reporter),
            selectinload(CommercialReport.reviewed_by),
        )
        .where(CommercialReport.id == report_id)
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


def report_to_dict(report: CommercialReport) -> dict:
    return {
        "id": report.id,
        "commercial_id": report.commercial_id,
        "commercial_title": report.commercial.title if report.commercial else None,
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
