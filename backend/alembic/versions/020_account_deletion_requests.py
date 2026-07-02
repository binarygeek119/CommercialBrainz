"""Account deletion requests with optional point transfer

Revision ID: 020
Revises: 019
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

deletion_status = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "cancelled",
    name="accountdeletionstatus",
    create_type=False,
)


def upgrade() -> None:
    deletion_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "account_deletion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("points_to_transfer", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column(
            "status",
            deletion_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_deletion_requests_user_id", "account_deletion_requests", ["user_id"])
    op.create_index(
        "ix_account_deletion_requests_recipient_id", "account_deletion_requests", ["recipient_id"]
    )
    op.create_index(
        "ix_account_deletion_requests_status", "account_deletion_requests", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_deletion_requests_status", table_name="account_deletion_requests")
    op.drop_index("ix_account_deletion_requests_recipient_id", table_name="account_deletion_requests")
    op.drop_index("ix_account_deletion_requests_user_id", table_name="account_deletion_requests")
    op.drop_table("account_deletion_requests")
    deletion_status.drop(op.get_bind(), checkfirst=True)
