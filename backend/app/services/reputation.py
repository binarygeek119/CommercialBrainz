"""User reputation points and concurrent submit slot limits."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Edit,
    EditStatus,
    EditType,
    ReputationCategory,
    ReputationEvent,
    User,
    UserRole,
    Vote,
    VoteChoice,
)

settings = get_settings()

QUALITY_EDIT_TYPES = {
    EditType.EDIT_VIDEO,
    EditType.EDIT_COMMERCIAL,
    EditType.ADD_TAG,
    EditType.ADD_CREDIT,
    EditType.MERGE_COMMERCIAL,
    EditType.SPLIT_COMMERCIAL,
}

VERSION_EDIT_TYPES = {
    EditType.CREATE_VIDEO,
    EditType.CREATE_COMMERCIAL,
}


def _points_value() -> Decimal:
    return Decimal(str(settings.reputation_point_value))


def _user_reputation_points(user: User) -> Decimal:
    raw = user.reputation_points
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


def max_submit_slots(user: User) -> int:
    if user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor:
        return settings.submit_slots_max
    points = _user_reputation_points(user)
    per_slot = Decimal(str(settings.submit_slots_points_per_slot))
    bonus = int(points // per_slot) if per_slot > 0 else 0
    return min(settings.submit_slots_max, settings.submit_slots_base + bonus)


def slots_bypassed(user: User) -> bool:
    return user.role in (UserRole.MOD, UserRole.ADMIN) or user.is_auto_editor


async def count_open_submissions(db: AsyncSession, user_id: UUID) -> int:
    result = await db.scalar(
        select(func.count())
        .select_from(Edit)
        .where(Edit.editor_id == user_id, Edit.status == EditStatus.OPEN)
    )
    return int(result or 0)


async def submit_slot_info(db: AsyncSession, user: User) -> dict[str, int | float]:
    max_slots = max_submit_slots(user)
    used = await count_open_submissions(db, user.id)
    return {
        "reputation_points": float(_user_reputation_points(user)),
        "submit_slots_max": max_slots,
        "submit_slots_used": used,
        "submit_slots_available": max(0, max_slots - used),
    }


async def assert_can_submit(db: AsyncSession, user: User) -> None:
    if slots_bypassed(user):
        return
    max_slots = max_submit_slots(user)
    used = await count_open_submissions(db, user.id)
    if used >= max_slots:
        raise ValueError(
            f"No submit slots available ({used}/{max_slots}). "
            "Earn reputation from approved submissions to unlock more."
        )


async def award_reputation_for_applied_edit(db: AsyncSession, edit: Edit) -> None:
    """Award up to four reputation categories when a community-voted edit is applied."""
    if edit.status != EditStatus.APPLIED:
        return

    editor = await db.get(User, edit.editor_id)
    if not editor:
        return

    vote_result = await db.execute(select(Vote).where(Vote.edit_id == edit.id))
    votes = vote_result.scalars().all()
    yes_count = sum(1 for v in votes if v.choice == VoteChoice.YES)

    categories: list[ReputationCategory] = [ReputationCategory.APPROVAL]
    if yes_count >= 1:
        categories.append(ReputationCategory.LIKE)
    if edit.edit_type in QUALITY_EDIT_TYPES:
        categories.append(ReputationCategory.QUALITY)
    if edit.edit_type in VERSION_EDIT_TYPES:
        categories.append(ReputationCategory.VERSION)

    point_value = _points_value()
    total_awarded = Decimal("0")

    for category in categories:
        existing = await db.execute(
            select(ReputationEvent).where(
                ReputationEvent.edit_id == edit.id,
                ReputationEvent.category == category,
            )
        )
        if existing.scalar_one_or_none():
            continue

        db.add(
            ReputationEvent(
                user_id=editor.id,
                edit_id=edit.id,
                category=category,
                points=point_value,
            )
        )
        total_awarded += point_value

    if total_awarded > 0:
        editor.reputation_points = float(_user_reputation_points(editor) + total_awarded)
        await db.flush()
