"""Add advertiser logo_url and edit_advertiser edit type

Revision ID: 013
Revises: 012
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("advertisers", sa.Column("logo_url", sa.String(512), nullable=True))
    op.execute("ALTER TYPE edittype ADD VALUE IF NOT EXISTS 'edit_advertiser'")


def downgrade() -> None:
    op.drop_column("advertisers", "logo_url")
