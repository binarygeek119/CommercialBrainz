"""User content reports for commercials and brands.

Revision ID: 027
Revises: 026
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

report_reason = postgresql.ENUM(
    "banned",
    "adult_ad",
    "adult_porn",
    "hate_speech",
    "other",
    name="contentreportreason",
    create_type=False,
)

report_status = postgresql.ENUM(
    "pending",
    "under_review",
    "resolved",
    "dismissed",
    name="contentreportstatus",
    create_type=False,
)


def upgrade() -> None:
    report_reason.create(op.get_bind(), checkfirst=True)
    report_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "content_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commercial_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("advertiser_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", report_reason, nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "status",
            report_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "(commercial_id IS NULL) <> (advertiser_id IS NULL)",
            name="ck_content_reports_one_target",
        ),
        sa.ForeignKeyConstraint(
            ["commercial_id"], ["commercials.sbid"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["advertiser_id"], ["advertisers.sbid"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_reports_commercial_id", "content_reports", ["commercial_id"]
    )
    op.create_index(
        "ix_content_reports_advertiser_id", "content_reports", ["advertiser_id"]
    )
    op.create_index("ix_content_reports_reporter_id", "content_reports", ["reporter_id"])
    op.create_index("ix_content_reports_status", "content_reports", ["status"])
    op.create_index(
        "uq_content_reports_open_commercial",
        "content_reports",
        ["commercial_id", "reporter_id"],
        unique=True,
        postgresql_where=sa.text(
            "commercial_id IS NOT NULL AND status IN ('pending', 'under_review')"
        ),
    )
    op.create_index(
        "uq_content_reports_open_advertiser",
        "content_reports",
        ["advertiser_id", "reporter_id"],
        unique=True,
        postgresql_where=sa.text(
            "advertiser_id IS NOT NULL AND status IN ('pending', 'under_review')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_content_reports_open_advertiser", table_name="content_reports")
    op.drop_index("uq_content_reports_open_commercial", table_name="content_reports")
    op.drop_index("ix_content_reports_status", table_name="content_reports")
    op.drop_index("ix_content_reports_reporter_id", table_name="content_reports")
    op.drop_index("ix_content_reports_advertiser_id", table_name="content_reports")
    op.drop_index("ix_content_reports_commercial_id", table_name="content_reports")
    op.drop_table("content_reports")
    report_status.drop(op.get_bind(), checkfirst=True)
    report_reason.drop(op.get_bind(), checkfirst=True)
