"""Brand logo gallery with popularity voting

Revision ID: 015
Revises: 014
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logopopularitychoice = postgresql.ENUM(
    "up", "down", name="logopopularitychoice", create_type=False
)


def upgrade() -> None:
    op.execute("ALTER TYPE edittype ADD VALUE IF NOT EXISTS 'add_advertiser_logo'")

    logopopularitychoice.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "advertiser_logos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "advertiser_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("advertisers.sbid", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("image_url", sa.String(512), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "edit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("edits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("popularity_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "advertiser_logo_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "logo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("advertiser_logos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "voter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "choice",
            logopopularitychoice,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("logo_id", "voter_id", name="uq_logo_voter"),
    )

    op.add_column(
        "advertisers",
        sa.Column(
            "main_logo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("advertiser_logos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO advertiser_logos (id, advertiser_id, image_url, label, popularity_score, created_at)
            SELECT gen_random_uuid(), sbid, logo_url, 'Imported logo', 1, created_at
            FROM advertisers
            WHERE logo_url IS NOT NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE advertisers a
            SET main_logo_id = l.id
            FROM advertiser_logos l
            WHERE l.advertiser_id = a.sbid
              AND a.logo_url IS NOT NULL
              AND a.main_logo_id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("advertisers", "main_logo_id")
    op.drop_table("advertiser_logo_votes")
    op.drop_table("advertiser_logos")
    logopopularitychoice.drop(op.get_bind(), checkfirst=True)
