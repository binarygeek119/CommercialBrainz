"""Add split_commercial edit type for breaking links into own commercials.

Revision ID: 022
Revises: 021
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE edittype ADD VALUE IF NOT EXISTS 'split_commercial'")


def downgrade() -> None:
    pass
