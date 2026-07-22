"""Add spoof commercial type.

Revision ID: 034
Revises: 033
"""

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE commercialtype ADD VALUE IF NOT EXISTS 'spoof'")


def downgrade() -> None:
    # PostgreSQL cannot easily remove enum values; leave 'spoof' in commercialtype.
    pass
