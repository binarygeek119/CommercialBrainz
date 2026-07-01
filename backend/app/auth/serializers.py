from app.auth.security import user_can_submit
from app.models import User
from app.schemas import UserPublic


def user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        access_level=user.access_level.value,
        can_submit=user_can_submit(user),
        is_auto_editor=user.is_auto_editor,
        accepted_edits_count=user.accepted_edits_count,
        submission_terms_version=user.submission_terms_version,
        created_at=user.created_at,
    )
