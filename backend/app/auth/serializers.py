from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    user_bulk_submit_granted,
    user_can_bulk_submit,
    user_can_submit,
)
from app.models import User
from app.schemas import UserPublic
from app.services.power_user_terms import active_power_user_terms_version
from app.services.reputation import max_submit_slots, submit_slot_info


async def user_to_public(db: AsyncSession, user: User) -> UserPublic:
    slots = await submit_slot_info(db, user)
    terms_version = await active_power_user_terms_version(db)
    # Hide bulk flags from clients that are not granted (still return false).
    show_bulk = user_bulk_submit_granted(user)
    can_bulk = user_can_bulk_submit(user, active_terms_version=terms_version) if show_bulk else False
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        access_level=user.access_level.value,
        can_submit=user_can_submit(user),
        email_verified=user.email_verified,
        reputation_points=slots["reputation_points"],
        submit_slots_max=slots["submit_slots_max"],
        submit_slots_used=slots["submit_slots_used"],
        submit_slots_available=slots["submit_slots_available"],
        is_auto_editor=user.is_auto_editor,
        accepted_edits_count=user.accepted_edits_count,
        submission_terms_version=user.submission_terms_version,
        submission_terms_accepted_at=user.submission_terms_accepted_at,
        bulk_submit_enabled=show_bulk,
        can_bulk_submit=can_bulk,
        power_user_terms_version=user.power_user_terms_version if show_bulk else None,
        power_user_terms_accepted_at=user.power_user_terms_accepted_at if show_bulk else None,
        created_at=user.created_at,
    )


def user_to_public_basic(user: User) -> UserPublic:
    """Sync serializer without open-slot counts (admin list)."""
    max_slots = max_submit_slots(user)
    points = float(user.reputation_points or 0)
    show_bulk = user_bulk_submit_granted(user)
    can_bulk = show_bulk and user.power_user_terms_version is not None
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        access_level=user.access_level.value,
        can_submit=user_can_submit(user),
        email_verified=user.email_verified,
        reputation_points=points,
        submit_slots_max=max_slots,
        submit_slots_used=0,
        submit_slots_available=max_slots,
        is_auto_editor=user.is_auto_editor,
        accepted_edits_count=user.accepted_edits_count,
        submission_terms_version=user.submission_terms_version,
        submission_terms_accepted_at=user.submission_terms_accepted_at,
        # Admin list still shows the stored flag so enable/disable UI stays accurate.
        bulk_submit_enabled=bool(user.bulk_submit_enabled),
        can_bulk_submit=can_bulk,
        power_user_terms_version=user.power_user_terms_version,
        power_user_terms_accepted_at=user.power_user_terms_accepted_at,
        created_at=user.created_at,
    )
