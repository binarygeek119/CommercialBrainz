"""Add YouTube link-check status columns for monthly dead-link scans.

Revision ID: 025
Revises: 024
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

_LINK_CHECK_STATUS = postgresql.ENUM(
    "ok",
    "unavailable",
    "private",
    "age_restricted",
    "error",
    name="videolinkcheckstatus",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE videolinkcheckstatus AS ENUM
                ('ok', 'unavailable', 'private', 'age_restricted', 'error');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.add_column(
        "videos",
        sa.Column(
            "link_check_status",
            _LINK_CHECK_STATUS,
            nullable=True,
        ),
    )
    op.add_column(
        "videos",
        sa.Column("link_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("link_check_detail", sa.Text(), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("link_flagged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_videos_link_check_status",
        "videos",
        ["link_check_status"],
    )
    op.create_index(
        "ix_videos_link_flagged_at",
        "videos",
        ["link_flagged_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_videos_link_flagged_at", table_name="videos")
    op.drop_index("ix_videos_link_check_status", table_name="videos")
    op.drop_column("videos", "link_flagged_at")
    op.drop_column("videos", "link_check_detail")
    op.drop_column("videos", "link_checked_at")
    op.drop_column("videos", "link_check_status")
    op.execute("DROP TYPE IF EXISTS videolinkcheckstatus")
