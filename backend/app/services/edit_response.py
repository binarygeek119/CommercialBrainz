"""Build EditPublic responses with optional fingerprint preview."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Edit, Vote
from app.schemas import EditPublic, FingerprintPreviewPublic, VotePublic
from app.services.fingerprint_queries import fingerprint_to_dict, get_preview_fingerprint


async def build_edit_public(db: AsyncSession, edit: Edit, votes: list[Vote] | None = None) -> EditPublic:
    vote_list = votes if votes is not None else list(edit.votes)
    fingerprint_preview = None
    if edit.edit_type.value == "create_video":
        fp = await get_preview_fingerprint(db, edit.id)
        fp_dict = fingerprint_to_dict(fp)
        if fp_dict:
            fingerprint_preview = FingerprintPreviewPublic(**fp_dict)

    return EditPublic(
        id=edit.id,
        edit_type=edit.edit_type.value,
        status=edit.status.value,
        entity_type=edit.entity_type,
        entity_id=edit.entity_id,
        before_state=edit.before_state,
        after_state=edit.after_state,
        editor_id=edit.editor_id,
        comment=edit.comment,
        expires_at=edit.expires_at,
        closed_at=edit.closed_at,
        created_at=edit.created_at,
        votes=[
            VotePublic(
                id=v.id,
                voter_id=v.voter_id,
                choice=v.choice.value,
                comment=v.comment,
                created_at=v.created_at,
            )
            for v in vote_list
        ],
        fingerprint_preview=fingerprint_preview,
    )
