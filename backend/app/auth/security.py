import bcrypt
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, UserRole, UserAccess
from app.schemas import TokenData

settings = get_settings()

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(user_id: UUID, *, remember_me: bool = True) -> str:
    minutes = settings.access_token_expire_minutes if remember_me else settings.session_token_expire_minutes
    expire = datetime.now(UTC) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return TokenData(user_id=UUID(user_id) if user_id else None)
    except (JWTError, ValueError):
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


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
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
