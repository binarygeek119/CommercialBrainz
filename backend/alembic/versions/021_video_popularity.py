"""Video link popularity voting and main link selection per commercial.

Revision ID: 021
Revises: 020
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logopopularitychoice = postgresql.ENUM(
    "up", "down", name="logopopularitychoice", create_type=False
)


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("popularity_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "videos",
        sa.Column("version_label", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "commercials",
        sa.Column(
            "main_video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.sbid", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    logopopularitychoice.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "video_popularity_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.sbid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "voter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("choice", logopopularitychoice, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("video_id", "voter_id", name="uq_video_popularity_voter"),
    )
    op.create_index("ix_video_popularity_votes_video_id", "video_popularity_votes", ["video_id"])
    op.create_index("ix_video_popularity_votes_voter_id", "video_popularity_votes", ["voter_id"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE commercials c
            SET main_video_id = sub.sbid
            FROM (
                SELECT DISTINCT ON (commercial_id) commercial_id, sbid
                FROM videos
                WHERE visibility = 'public'
                ORDER BY commercial_id, created_at ASC
            ) sub
            WHERE c.sbid = sub.commercial_id
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_video_popularity_votes_voter_id", table_name="video_popularity_votes")
    op.drop_index("ix_video_popularity_votes_video_id", table_name="video_popularity_votes")
    op.drop_table("video_popularity_votes")
    op.drop_column("commercials", "main_video_id")
    op.drop_column("videos", "version_label")
    op.drop_column("videos", "popularity_score")
