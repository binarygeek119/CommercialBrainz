"""Domain and Cloud VM donation fund ledger + costs.

Revision ID: 038
Revises: 037
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

donation_fund = postgresql.ENUM(
    "domain",
    "cloud_vm",
    name="donationfund",
    create_type=False,
)


def upgrade() -> None:
    donation_fund.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "donation_fund_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fund", donation_fund, nullable=False),
        sa.Column("bmc_support_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("support_note", sa.Text(), nullable=True),
        sa.Column("supporter_name", sa.String(length=255), nullable=True),
        sa.Column("donated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bmc_support_id"),
    )
    op.create_index(
        "ix_donation_fund_entries_fund", "donation_fund_entries", ["fund"], unique=False
    )
    op.create_index(
        "ix_donation_fund_entries_bmc_support_id",
        "donation_fund_entries",
        ["bmc_support_id"],
        unique=False,
    )
    op.create_index(
        "ix_donation_fund_entries_donated_at",
        "donation_fund_entries",
        ["donated_at"],
        unique=False,
    )

    op.create_table(
        "donation_fund_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fund", donation_fund, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_donation_fund_costs_fund", "donation_fund_costs", ["fund"], unique=False
    )
    op.create_index(
        "ix_donation_fund_costs_paid_at", "donation_fund_costs", ["paid_at"], unique=False
    )

    # Seed donate_funds SiteSetting with tracking_started_at = now so historical
    # Buy Me a Coffee supporters are never counted.
    op.execute(
        sa.text(
            """
            INSERT INTO site_settings (key, value, updated_at)
            VALUES (
              'donate_funds',
              jsonb_build_object(
                'tracking_started_at', to_jsonb(now()),
                'domain', jsonb_build_object('goal', 0),
                'cloud_vm', jsonb_build_object('goal', 0),
                'last_sync_at', null,
                'last_sync_error', null
              ),
              now()
            )
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM site_settings WHERE key = 'donate_funds'"))
    op.drop_index("ix_donation_fund_costs_paid_at", table_name="donation_fund_costs")
    op.drop_index("ix_donation_fund_costs_fund", table_name="donation_fund_costs")
    op.drop_table("donation_fund_costs")
    op.drop_index("ix_donation_fund_entries_donated_at", table_name="donation_fund_entries")
    op.drop_index(
        "ix_donation_fund_entries_bmc_support_id", table_name="donation_fund_entries"
    )
    op.drop_index("ix_donation_fund_entries_fund", table_name="donation_fund_entries")
    op.drop_table("donation_fund_entries")
    donation_fund.drop(op.get_bind(), checkfirst=True)
