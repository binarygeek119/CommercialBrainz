"""Add edit_advertiser_logo edit type

Revision ID: 018
Revises: 017
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE edittype ADD VALUE IF NOT EXISTS 'edit_advertiser_logo'")


def downgrade() -> None:
    pass
