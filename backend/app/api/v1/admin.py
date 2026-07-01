from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users/{user_id}/role/{role}", response_model=UserPublic)
async def set_user_role(
    user_id: UUID,
    role: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        new_role = UserRole(role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid role") from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = new_role
    user.is_auto_editor = new_role in (UserRole.MOD, UserRole.ADMIN)
    await db.flush()
    return user
