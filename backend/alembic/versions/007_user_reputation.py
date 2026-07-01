"""User reputation points and event ledger

Revision ID: 007
Revises: 006
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reputation_points", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE reputationcategory AS ENUM ('approval', 'like', 'quality', 'version');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    category_enum = postgresql.ENUM(
        "approval", "like", "quality", "version", name="reputationcategory", create_type=False
    )

    op.create_table(
        "reputation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("edit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edits.id"), nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("points", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("edit_id", "category", name="uq_reputation_events_edit_category"),
    )
    op.create_index("ix_reputation_events_user_id", "reputation_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_reputation_events_user_id", table_name="reputation_events")
    op.drop_table("reputation_events")
    op.execute("DROP TYPE IF EXISTS reputationcategory")
    op.drop_column("users", "reputation_points")
