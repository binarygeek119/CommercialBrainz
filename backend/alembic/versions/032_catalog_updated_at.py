"""Add updated_at to advertisers and catalog entities.

Revision ID: 032
Revises: 031
"""

import sqlalchemy as sa

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None

TABLES = ("advertisers", "stores", "services", "events", "holidays")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.execute(sa.text(f"UPDATE {table} SET updated_at = created_at"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_column(table, "updated_at")
