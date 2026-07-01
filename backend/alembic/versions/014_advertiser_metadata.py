"""Add structured metadata columns to advertisers

Revision ID: 014
Revises: 013
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("advertisers", sa.Column("website", sa.String(512), nullable=True))
    op.add_column("advertisers", sa.Column("country", sa.String(64), nullable=True))
    op.add_column("advertisers", sa.Column("founded_year", sa.Integer(), nullable=True))
    op.add_column("advertisers", sa.Column("industry", sa.String(128), nullable=True))
    op.add_column("advertisers", sa.Column("headquarters", sa.String(255), nullable=True))
    op.add_column("advertisers", sa.Column("parent_company", sa.String(255), nullable=True))
    op.add_column("advertisers", sa.Column("wikipedia_url", sa.String(512), nullable=True))
    op.add_column(
        "advertisers",
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("advertisers", "metadata")
    op.drop_column("advertisers", "wikipedia_url")
    op.drop_column("advertisers", "parent_company")
    op.drop_column("advertisers", "headquarters")
    op.drop_column("advertisers", "industry")
    op.drop_column("advertisers", "founded_year")
    op.drop_column("advertisers", "country")
    op.drop_column("advertisers", "website")
