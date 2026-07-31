"""Community YouTube cookie donation backlog.

Revision ID: 036
Revises: 035
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

cookie_donation_status = postgresql.ENUM(
    "pending",
    "active",
    "exhausted",
    "rejected",
    name="cookiedonationstatus",
    create_type=False,
)


def upgrade() -> None:
    cookie_donation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cookie_donations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            cookie_donation_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("cookies_text", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agreement_accepted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("donor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("donor_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exhausted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["donor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cookie_donations_status", "cookie_donations", ["status"], unique=False
    )
    op.create_index(
        "ix_cookie_donations_created_at", "cookie_donations", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_cookie_donations_created_at", table_name="cookie_donations")
    op.drop_index("ix_cookie_donations_status", table_name="cookie_donations")
    op.drop_table("cookie_donations")
    cookie_donation_status.drop(op.get_bind(), checkfirst=True)
