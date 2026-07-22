"""Add queued status for bulk playlist staging window.

Revision ID: 033
Revises: 032
"""

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE bulksubmissionitemstatus ADD VALUE IF NOT EXISTS 'queued'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely.
    pass
