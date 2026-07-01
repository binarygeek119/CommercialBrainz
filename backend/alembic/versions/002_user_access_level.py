"""Add user access level for vote-only vs submit-and-vote

Revision ID: 002
Revises: 001
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_access = postgresql.ENUM("vote_only", "submit_and_vote", name="useraccess", create_type=True)
    user_access.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "access_level",
            user_access,
            nullable=False,
            server_default="vote_only",
        ),
    )
    op.execute(
        "UPDATE users SET access_level = 'submit_and_vote' WHERE role IN ('mod', 'admin')"
    )


def downgrade() -> None:
    op.drop_column("users", "access_level")
    op.execute("DROP TYPE IF EXISTS useraccess")
