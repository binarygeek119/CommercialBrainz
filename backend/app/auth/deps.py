from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token, get_user_by_id, user_email_verified, user_is_admin, user_is_mod, user_can_submit
from app.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    token_data = decode_access_token(credentials.credentials)
    if not token_data.user_id:
        return None
    user = await get_user_by_id(db, token_data.user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_submitter(user: User = Depends(get_current_user)) -> User:
    if not user_email_verified(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email address before submitting edits.",
        )
    if not user_can_submit(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission access required. Complete the submission terms quiz to upgrade your account.",
        )
    return user


async def require_mod(user: User = Depends(get_current_user)) -> User:
    if not user_is_mod(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Moderator access required")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user_is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
