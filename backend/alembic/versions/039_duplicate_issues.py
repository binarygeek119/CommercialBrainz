"""Community duplicate-issue voting tables.

Revision ID: 039
Revises: 038
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

issue_status = postgresql.ENUM(
    "open",
    "resolved",
    "superseded",
    name="duplicateissuestatus",
    create_type=False,
)

vote_choice = postgresql.ENUM(
    "add_as_sub_link",
    "remove_from_database",
    "make_master_link",
    name="duplicatevotechoice",
    create_type=False,
)


def upgrade() -> None:
    issue_status.create(op.get_bind(), checkfirst=True)
    vote_choice.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "duplicate_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", issue_status, nullable=False, server_default="open"),
        sa.Column("video_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("best_match_type", sa.String(length=64), nullable=True),
        sa.Column("hamming_distance", sa.Integer(), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resolved_choice", vote_choice, nullable=True),
        sa.Column("resolved_subject_video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("video_a_id < video_b_id", name="ck_duplicate_issues_canonical_pair"),
        sa.ForeignKeyConstraint(["video_a_id"], ["videos.sbid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_b_id"], ["videos.sbid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resolved_subject_video_id"], ["videos.sbid"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "video_a_id",
            "video_b_id",
            "generation",
            name="uq_duplicate_issue_pair_generation",
        ),
    )
    op.create_index("ix_duplicate_issues_status", "duplicate_issues", ["status"])
    op.create_index("ix_duplicate_issues_video_a_id", "duplicate_issues", ["video_a_id"])
    op.create_index("ix_duplicate_issues_video_b_id", "duplicate_issues", ["video_b_id"])

    op.create_table(
        "duplicate_issue_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("choice", vote_choice, nullable=False),
        sa.Column("subject_video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["duplicate_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_video_id"], ["videos.sbid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id", "voter_id", name="uq_duplicate_issue_voter"),
    )
    op.create_index("ix_duplicate_issue_votes_issue_id", "duplicate_issue_votes", ["issue_id"])
    op.create_index("ix_duplicate_issue_votes_voter_id", "duplicate_issue_votes", ["voter_id"])


def downgrade() -> None:
    op.drop_table("duplicate_issue_votes")
    op.drop_table("duplicate_issues")
    vote_choice.drop(op.get_bind(), checkfirst=True)
    issue_status.drop(op.get_bind(), checkfirst=True)
