"""Add bumper commercial type and bumper_channel.

Revision ID: 030
Revises: 029
"""

import sqlalchemy as sa

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE commercialtype ADD VALUE IF NOT EXISTS 'bumper'")
    op.add_column(
        "commercials",
        sa.Column("bumper_channel", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("commercials", "bumper_channel")
    # PostgreSQL cannot easily remove enum values; leave 'bumper' in commercialtype.
