"""User announcement acknowledgements for login popups.

Revision ID: 037
Revises: 036
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_announcement_acks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("announcement_id", sa.String(length=64), nullable=False),
        sa.Column(
            "acked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "announcement_id", name="uq_user_announcement_ack"
        ),
    )
    op.create_index(
        op.f("ix_user_announcement_acks_user_id"),
        "user_announcement_acks",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_announcement_acks_announcement_id"),
        "user_announcement_acks",
        ["announcement_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_announcement_acks_announcement_id"),
        table_name="user_announcement_acks",
    )
    op.drop_index(
        op.f("ix_user_announcement_acks_user_id"),
        table_name="user_announcement_acks",
    )
    op.drop_table("user_announcement_acks")
