"""Email verification token creation and validation."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import EmailVerificationToken, User
from app.services.email import send_verification_email, smtp_configured
from app.services.password_reset import hash_reset_token

logger = logging.getLogger(__name__)


async def send_verification_email_for_user(
    db: AsyncSession, user: User
) -> bool:
    """Create verification token and email link. Returns True if email was sent."""
    if user.email_verified:
        return True

    settings = get_settings()
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
        reason = "not configured" if not smtp_configured() else "send failed"
        logger.warning(
            "Verification email not sent (SMTP %s). Verify link for %s: %s",
            reason,
            user.email,
            verify_url,
        )
    return sent


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
    sent = await send_verification_email_for_user(db, user)
    if not sent:
        if not smtp_configured():
            raise RuntimeError(
                "Email delivery is not configured on this server. "
                "Set SMTP_HOST (and credentials) in the app .env, then restart the API."
            )
        raise RuntimeError(
            "Could not send the verification email. Try again later or contact an admin."
        )
