"""Activate submission terms version 2 (master/sub links, split vote rules).

Revision ID: 023
Revises: 022
Create Date: 2026-07-02
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.data.submission_terms_v2 import SUBMISSION_TERMS_V2

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE submission_terms_documents SET is_active = false WHERE is_active = true"
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO submission_terms_documents (id, version, title, intro, sections, is_active)
            VALUES (gen_random_uuid(), :version, :title, :intro, CAST(:sections AS jsonb), true)
            """
        ),
        {
            "version": SUBMISSION_TERMS_V2["version"],
            "title": SUBMISSION_TERMS_V2["title"],
            "intro": SUBMISSION_TERMS_V2["intro"],
            "sections": json.dumps(SUBMISSION_TERMS_V2["sections"]),
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM submission_terms_documents WHERE version = 2")
    )
    bind.execute(
        sa.text(
            """
            UPDATE submission_terms_documents
            SET is_active = true
            WHERE version = (
                SELECT MAX(version) FROM submission_terms_documents WHERE version < 2
            )
            """
        )
    )
