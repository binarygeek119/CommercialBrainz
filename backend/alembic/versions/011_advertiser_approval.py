"""Brand approval status and create_advertiser edit type

Revision ID: 011
Revises: 010
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    advertiser_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="advertiserstatus",
        create_type=True,
    )
    advertiser_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "advertisers",
        sa.Column(
            "status",
            advertiser_status,
            nullable=False,
            server_default="approved",
        ),
    )
    op.create_index("ix_advertisers_status", "advertisers", ["status"])

    op.execute("ALTER TYPE edittype ADD VALUE IF NOT EXISTS 'create_advertiser'")


def downgrade() -> None:
    op.drop_index("ix_advertisers_status", table_name="advertisers")
    op.drop_column("advertisers", "status")
    op.execute("DROP TYPE IF EXISTS advertiserstatus")
