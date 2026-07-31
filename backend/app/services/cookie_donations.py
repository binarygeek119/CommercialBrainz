"""Community YouTube cookie donation backlog for yt-dlp."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CookieDonation, CookieDonationStatus, User
from app.services.cookie_crypto import decrypt_cookies, encrypt_cookies
from app.services.ytdlp_cookies import (
    resolve_cookies_path,
    save_cookies_text,
    validate_cookies_text,
)

logger = logging.getLogger(__name__)


def donation_public_dict(row: CookieDonation) -> dict[str, Any]:
    """Public/admin list representation — never includes cookie contents."""
    return {
        "id": row.id,
        "status": row.status.value,
        "size_bytes": row.size_bytes,
        "agreement_accepted": row.agreement_accepted,
        "donor_note": row.donor_note,
        "activated_at": row.activated_at,
        "exhausted_at": row.exhausted_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "encrypted": True,
    }


async def backlog_counts(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(CookieDonation.status, func.count())
        .group_by(CookieDonation.status)
    )
    counts = {status.value: 0 for status in CookieDonationStatus}
    for status, n in result.all():
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = int(n)
    return counts


async def submit_cookie_donation(
    db: AsyncSession,
    *,
    cookies: str,
    agreement_accepted: bool,
    donor_note: str | None = None,
    donor: User | None = None,
) -> CookieDonation:
    if not agreement_accepted:
        raise ValueError("You must accept the cookie donation agreement")
    cleaned = validate_cookies_text(cookies)
    ciphertext = encrypt_cookies(cleaned)
    row = CookieDonation(
        status=CookieDonationStatus.PENDING,
        cookies_text=ciphertext,
        size_bytes=len(cleaned.encode("utf-8")),
        agreement_accepted=True,
        donor_id=donor.id if donor else None,
        donor_note=(donor_note or "").strip()[:500] or None,
    )
    db.add(row)
    await db.flush()

    # If nothing is active for yt-dlp yet, promote this donation immediately.
    if resolve_cookies_path() is None:
        await activate_donation(db, row)
    return row


async def list_cookie_donations(
    db: AsyncSession,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[CookieDonation]:
    query = select(CookieDonation)
    if status:
        query = query.where(CookieDonation.status == CookieDonationStatus(status))
    result = await db.execute(
        query.order_by(CookieDonation.created_at.asc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def get_cookie_donation(db: AsyncSession, donation_id: UUID) -> CookieDonation | None:
    return await db.get(CookieDonation, donation_id)


async def activate_donation(db: AsyncSession, row: CookieDonation) -> CookieDonation:
    """Decrypt this donation, write the managed cookies file, and mark it active."""
    # Exhaust any currently active donation rows.
    result = await db.execute(
        select(CookieDonation).where(CookieDonation.status == CookieDonationStatus.ACTIVE)
    )
    now = datetime.now(UTC)
    for active in result.scalars().all():
        if active.id == row.id:
            continue
        active.status = CookieDonationStatus.EXHAUSTED
        active.exhausted_at = now
        active.updated_at = now

    plaintext = decrypt_cookies(row.cookies_text)
    save_cookies_text(plaintext)
    # Re-encrypt with current seed in case the row was legacy plaintext.
    row.cookies_text = encrypt_cookies(plaintext)
    row.status = CookieDonationStatus.ACTIVE
    row.activated_at = now
    row.exhausted_at = None
    row.updated_at = now
    await db.flush()
    logger.info("Activated cookie donation %s", row.id)
    return row


async def activate_next_pending(db: AsyncSession) -> CookieDonation | None:
    """Promote the oldest pending donation into the live cookies file."""
    result = await db.execute(
        select(CookieDonation)
        .where(CookieDonation.status == CookieDonationStatus.PENDING)
        .order_by(CookieDonation.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return await activate_donation(db, row)


async def rotate_exhausted_to_next(db: AsyncSession) -> CookieDonation | None:
    """
    Mark the active donation exhausted and activate the next pending one.

    Used when the current YouTube cookies stop working (bot check / expired).
    """
    result = await db.execute(
        select(CookieDonation).where(CookieDonation.status == CookieDonationStatus.ACTIVE)
    )
    now = datetime.now(UTC)
    for active in result.scalars().all():
        active.status = CookieDonationStatus.EXHAUSTED
        active.exhausted_at = now
        active.updated_at = now
    await db.flush()
    return await activate_next_pending(db)


async def reject_donation(
    db: AsyncSession,
    row: CookieDonation,
    *,
    reviewer: User,
    notes: str | None = None,
) -> CookieDonation:
    if row.status == CookieDonationStatus.ACTIVE:
        raise ValueError("Cannot reject the active donation; rotate to the next one first")
    row.status = CookieDonationStatus.REJECTED
    row.reviewed_by_id = reviewer.id
    row.review_notes = (notes or "").strip()[:1000] or None
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row
