from contextvars import ContextVar

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    decode_access_token,
    get_user_by_id,
    user_can_submit,
    user_email_verified,
    user_is_admin,
    user_is_mod,
)
from app.database import get_db
from app.models import User
from app.services.api_tokens import API_TOKEN_PREFIX, authenticate_api_token

security = HTTPBearer(auto_error=False)

_read_only_api_token: ContextVar[bool] = ContextVar("read_only_api_token", default=False)


def auth_is_read_only() -> bool:
    return _read_only_api_token.get()


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    _read_only_api_token.set(False)

    raw: str | None = None
    if credentials and credentials.credentials:
        raw = credentials.credentials.strip()
    elif api_key and api_key.strip():
        raw = api_key.strip()

    if not raw:
        return None

    token_data = decode_access_token(raw)
    if token_data.user_id:
        user = await get_user_by_id(db, token_data.user_id)
        if user and user.is_active:
            return user
        return None

    if raw.startswith(API_TOKEN_PREFIX):
        user = await authenticate_api_token(db, raw)
        if user:
            _read_only_api_token.set(True)
            return user

    return None


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_data = decode_access_token(credentials.credentials)
    if not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Use your account login token to manage API keys",
        )
    user = await get_user_by_id(db, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_write_access(
    user: User = Depends(get_current_user),
) -> User:
    if auth_is_read_only():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only API token cannot perform write operations",
        )
    return user


async def require_submitter(user: User = Depends(require_write_access)) -> User:
    if not user_email_verified(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email address before submitting edits.",
        )
    if not user_can_submit(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Submission access required. Complete the submission terms "
                "quiz to upgrade your account."
            ),
        )
    return user


async def require_mod(user: User = Depends(require_write_access)) -> User:
    if not user_is_mod(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required",
        )
    return user


async def require_admin(user: User = Depends(require_write_access)) -> User:
    if not user_is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
