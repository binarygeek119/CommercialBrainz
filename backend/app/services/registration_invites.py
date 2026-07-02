"""Registration invite-only mode and invite code management."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RegistrationInvite, SiteSetting, User

settings = get_settings()

INVITE_ONLY_KEY = "registration_invite_only"


def _normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def _format_code(raw: str) -> str:
    """Store/display as XXXX-XXXX-XXXX groups when long enough."""
    normalized = _normalize_code(raw)
    if len(normalized) <= 8:
        return normalized
    chunks = [normalized[i : i + 4] for i in range(0, len(normalized), 4)]
    return "-".join(chunks)


def generate_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    return _format_code(raw)


async def _get_setting(db: AsyncSession, key: str) -> SiteSetting | None:
    return await db.get(SiteSetting, key)


async def is_registration_invite_only(db: AsyncSession) -> bool:
    row = await _get_setting(db, INVITE_ONLY_KEY)
    if row and isinstance(row.value, dict):
        return bool(row.value.get("enabled"))
    return settings.registration_invite_only


async def set_registration_invite_only(db: AsyncSession, enabled: bool) -> bool:
    row = await _get_setting(db, INVITE_ONLY_KEY)
    if row is None:
        row = SiteSetting(key=INVITE_ONLY_KEY, value={"enabled": enabled})
        db.add(row)
    else:
        row.value = {**row.value, "enabled": enabled}
        row.updated_at = datetime.now(UTC)
    await db.flush()
    return enabled


def invite_is_valid(invite: RegistrationInvite, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if invite.revoked_at is not None:
        return False
    if invite.expires_at is not None and invite.expires_at <= now:
        return False
    return invite.use_count < invite.max_uses


async def get_invite_by_code(db: AsyncSession, code: str) -> RegistrationInvite | None:
    from sqlalchemy import func as sa_func

    normalized = _normalize_code(code)
    if not normalized:
        return None
    compact = sa_func.replace(sa_func.replace(sa_func.upper(RegistrationInvite.code), "-", ""), " ", "")
    result = await db.execute(select(RegistrationInvite).where(compact == normalized))
    return result.scalar_one_or_none()


async def validate_invite_code(db: AsyncSession, code: str) -> RegistrationInvite:
    invite = await get_invite_by_code(db, code)
    if not invite or not invite_is_valid(invite):
        raise ValueError("Invalid or expired invite code")
    return invite


async def consume_invite(db: AsyncSession, invite: RegistrationInvite) -> None:
    if not invite_is_valid(invite):
        raise ValueError("Invalid or expired invite code")
    invite.use_count += 1
    await db.flush()


async def create_registration_invite(
    db: AsyncSession,
    *,
    created_by: User | None,
    label: str | None = None,
    max_uses: int = 1,
    expires_in_days: int | None = 30,
) -> RegistrationInvite:
    if max_uses < 1:
        raise ValueError("max_uses must be at least 1")

    expires_at = None
    if expires_in_days is not None and expires_in_days > 0:
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

    for _ in range(10):
        code = generate_invite_code()
        existing = await get_invite_by_code(db, code)
        if existing is None:
            invite = RegistrationInvite(
                code=code,
                label=label,
                max_uses=max_uses,
                created_by_id=created_by.id if created_by else None,
                expires_at=expires_at,
            )
            db.add(invite)
            await db.flush()
            return invite
    raise RuntimeError("Could not generate a unique invite code")


async def list_registration_invites(
    db: AsyncSession,
    *,
    include_revoked: bool = False,
    limit: int = 100,
) -> list[RegistrationInvite]:
    stmt = select(RegistrationInvite).order_by(RegistrationInvite.created_at.desc()).limit(limit)
    if not include_revoked:
        stmt = stmt.where(RegistrationInvite.revoked_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_registration_invite(db: AsyncSession, invite_id: UUID) -> RegistrationInvite:
    invite = await db.get(RegistrationInvite, invite_id)
    if not invite:
        raise ValueError("Invite not found")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        await db.flush()
    return invite


def invite_to_public(invite: RegistrationInvite) -> dict:
    return {
        "id": invite.id,
        "code": invite.code,
        "label": invite.label,
        "max_uses": invite.max_uses,
        "use_count": invite.use_count,
        "revoked_at": invite.revoked_at,
        "expires_at": invite.expires_at,
        "created_at": invite.created_at,
        "remaining_uses": max(0, invite.max_uses - invite.use_count),
        "is_active": invite_is_valid(invite),
    }
