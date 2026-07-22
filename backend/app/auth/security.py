from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, UserAccess, UserRole
from app.schemas import TokenData

settings = get_settings()

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(user_id: UUID, *, remember_me: bool = True) -> str:
    minutes = (
        settings.access_token_expire_minutes
        if remember_me
        else settings.session_token_expire_minutes
    )
    expire = datetime.now(UTC) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return TokenData(user_id=UUID(user_id) if user_id else None)
    except (InvalidTokenError, ValueError, TypeError):
        return TokenData(user_id=None)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, login: str, password: str) -> User | None:
    login = login.strip()
    user = await get_user_by_username(db, login)
    if not user and "@" in login:
        user = await get_user_by_email(db, login)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def user_email_verified(user: User) -> bool:
    if user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor:
        return True
    return user.email_verified


def user_can_submit(user: User) -> bool:
    if user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor:
        return True
    return user.access_level == UserAccess.SUBMIT_AND_VOTE


def user_can_vote(user: User) -> bool:
    if user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor:
        return True
    if not user.email_verified:
        return False
    account_age = datetime.now(UTC) - user.created_at.replace(tzinfo=UTC)
    return (
        account_age.days >= settings.voting_min_account_days
        and user.accepted_edits_count >= settings.voting_min_accepted_edits
    )


def user_is_mod(user: User) -> bool:
    return user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor


def user_is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def user_bulk_submit_eligible(user: User) -> bool:
    """Eligible for admin to enable bulk submit (500+ rep or mod/admin)."""
    if user.role in (UserRole.MOD, UserRole.ADMIN):
        return True
    return float(user.reputation_points or 0) >= settings.bulk_submit_min_reputation


def user_bulk_submit_granted(user: User) -> bool:
    """Admin has enabled bulk submit (may still need Power User Terms)."""
    return bool(user.bulk_submit_enabled) and user_bulk_submit_eligible(user)


def user_has_accepted_power_user_terms(user: User, active_version: int | None) -> bool:
    if active_version is None:
        return False
    return user.power_user_terms_version == active_version


def user_can_bulk_submit(user: User, *, active_terms_version: int | None = None) -> bool:
    """Full access: granted + eligible + accepted current Power User Terms."""
    if not user_bulk_submit_granted(user):
        return False
    if active_terms_version is None:
        # Callers that already recorded acceptance on the user row.
        return user.power_user_terms_version is not None
    return user_has_accepted_power_user_terms(user, active_terms_version)


def user_can_see_bulk_import_marker(user: User | None) -> bool:
    """Power users (granted), mods, and admins may see was-bulk-imported markers."""
    if not user:
        return False
    if user_is_mod(user):
        return True
    return bool(user.bulk_submit_enabled) and user_bulk_submit_eligible(user)