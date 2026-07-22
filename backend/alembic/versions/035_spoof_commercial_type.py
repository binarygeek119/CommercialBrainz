"""Add spoof commercial type.

Revision ID: 035
Revises: 034
"""

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE commercialtype ADD VALUE IF NOT EXISTS 'spoof'")


def downgrade() -> None:
    # PostgreSQL cannot easily remove enum values; leave 'spoof' in commercialtype.
    pass
