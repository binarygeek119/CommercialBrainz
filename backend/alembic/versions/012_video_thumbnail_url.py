"""Add thumbnail_url to videos

Revision ID: 012
Revises: 011
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("thumbnail_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "thumbnail_url")
