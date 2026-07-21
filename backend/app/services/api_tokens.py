"""Read-only API token (PKI key) management."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiToken, User

API_TOKEN_PREFIX = "cbz_ro_"
MAX_TOKENS_PER_USER = 10


def hash_api_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def token_display_prefix(raw_token: str) -> str:
    return raw_token[: len(API_TOKEN_PREFIX) + 8]


def generate_api_token() -> str:
    return f"{API_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


async def authenticate_api_token(db: AsyncSession, raw_token: str) -> User | None:
    if not raw_token.startswith(API_TOKEN_PREFIX):
        return None

    token_hash = hash_api_token(raw_token)
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    user = await db.get(User, record.user_id)
    if not user or not user.is_active:
        return None

    record.last_used_at = datetime.now(UTC)
    await db.flush()
    return user


async def list_user_api_tokens(db: AsyncSession, user_id: UUID) -> list[ApiToken]:
    result = await db.execute(
        select(ApiToken)
        .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
        .order_by(ApiToken.created_at.desc())
    )
    return list(result.scalars().all())


async def create_api_token(
    db: AsyncSession, user: User, label: str | None = None
) -> tuple[ApiToken, str]:
    count = await db.scalar(
        select(func.count())
        .select_from(ApiToken)
        .where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
    )
    if (count or 0) >= MAX_TOKENS_PER_USER:
        raise ValueError(f"Maximum of {MAX_TOKENS_PER_USER} active API tokens reached")

    raw_token = generate_api_token()
    record = ApiToken(
        user_id=user.id,
        token_hash=hash_api_token(raw_token),
        token_prefix=token_display_prefix(raw_token),
        label=label.strip() if label and label.strip() else None,
        scope="read_only",
    )
    db.add(record)
    await db.flush()
    return record, raw_token


async def revoke_api_token(db: AsyncSession, user_id: UUID, token_id: UUID) -> bool:
    result = await db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == user_id,
            ApiToken.revoked_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    record.revoked_at = datetime.now(UTC)
    await db.flush()
    return True


async def revoke_all_api_tokens(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(ApiToken).where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
    )
    now = datetime.now(UTC)
    count = 0
    for record in result.scalars():
        record.revoked_at = now
        count += 1
    if count:
        await db.flush()
    return count
