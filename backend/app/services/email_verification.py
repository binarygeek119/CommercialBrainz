"""Email verification token creation and validation."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import EmailVerificationToken, User
from app.services.email import send_verification_email
from app.services.password_reset import hash_reset_token

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_verification_email_for_user(
    db: AsyncSession, user: User) -> None:
    """Create verification token and email link. No-op if already verified."""
    if user.email_verified:
        return

    await db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )

    raw_token = secrets.token_urlsafe(32)
    token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.email_verification_expire_minutes),
    )
    db.add(token)
    await db.flush()

    base = settings.app_public_url.rstrip("/")
    verify_url = f"{base}/verify-email?token={raw_token}"
    sent = await send_verification_email(user.email, user.username, verify_url)
    if not sent:
        logger.warning(
            "Verification email not sent (SMTP unavailable). Verify link for %s: %s",
            user.email,
            verify_url,
        )


async def verify_email_with_token(db: AsyncSession, raw_token: str) -> User:
    token_hash = hash_reset_token(raw_token)
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    verify_token = result.scalar_one_or_none()
    if not verify_token or verify_token.used_at is not None:
        raise ValueError("Invalid or expired verification link")

    now = datetime.now(UTC)
    expires_at = verify_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        raise ValueError("Invalid or expired verification link")

    user = await db.get(User, verify_token.user_id)
    if not user or not user.is_active:
        raise ValueError("Invalid or expired verification link")

    user.email_verified = True
    user.email_verified_at = now
    verify_token.used_at = now
    await db.flush()
    return user


async def resend_verification_email(db: AsyncSession, user: User) -> None:
    if user.email_verified:
        raise ValueError("Email is already verified")
    await send_verification_email_for_user(db, user)
