"""Password reset token creation and validation."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PasswordResetToken, User
from app.services.email import send_password_reset_email

logger = logging.getLogger(__name__)
settings = get_settings()


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Create reset token and email link. Silent if user not found."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return

    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )

    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    db.add(token)
    await db.flush()

    reset_url = f"{settings.app_public_url.rstrip('/')}/reset-password?token={raw_token}"
    sent = await send_password_reset_email(user.email, user.username, reset_url)
    if not sent:
        logger.warning(
            "Password reset email not sent (SMTP unavailable). Reset link for %s: %s",
            user.email,
            reset_url,
        )


async def reset_password_with_token(db: AsyncSession, raw_token: str, new_password: str) -> User:
    from app.auth.security import hash_password

    token_hash = hash_reset_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalar_one_or_none()
    if not reset_token or reset_token.used_at is not None:
        raise ValueError("Invalid or expired reset link")

    now = datetime.now(UTC)
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        raise ValueError("Invalid or expired reset link")

    user = await db.get(User, reset_token.user_id)
    if not user or not user.is_active:
        raise ValueError("Invalid or expired reset link")

    user.hashed_password = hash_password(new_password)
    reset_token.used_at = now
    await db.flush()
    return user
