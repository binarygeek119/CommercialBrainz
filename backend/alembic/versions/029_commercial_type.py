"""Add commercial_type to commercials.

Revision ID: 029
Revises: 028
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

commercial_type = postgresql.ENUM(
    "general_ad",
    "psa",
    "service",
    "store",
    name="commercialtype",
    create_type=False,
)


def upgrade() -> None:
    commercial_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "commercials",
        sa.Column("commercial_type", commercial_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("commercials", "commercial_type")
    op.execute("DROP TYPE IF EXISTS commercialtype")
