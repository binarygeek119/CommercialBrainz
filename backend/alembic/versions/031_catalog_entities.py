"""Add Store, Service, Event, Holiday catalogs (Brand copies).

Revision ID: 031
Revises: 030
"""

# ruff: noqa: E501

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

EDIT_TYPES = [
    "create_store",
    "edit_store",
    "add_store_logo",
    "edit_store_logo",
    "create_service",
    "edit_service",
    "add_service_logo",
    "edit_service_logo",
    "create_event",
    "edit_event",
    "add_event_logo",
    "edit_event_logo",
    "create_holiday",
    "edit_holiday",
    "add_holiday_logo",
    "edit_holiday_logo",
]

catalogstatus = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    name="catalogstatus",
    create_type=False,
)


def _logo_votes(name: str, logo_table: str, uq_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "choice",
            postgresql.ENUM(
                "up",
                "down",
                name="logopopularitychoice",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["logo_id"], [f"{logo_table}.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("logo_id", "voter_id", name=uq_name),
    )
    op.create_index(f"ix_{name}_logo_id", name, ["logo_id"])
    op.create_index(f"ix_{name}_voter_id", name, ["voter_id"])


def _create_entity(table: str, extras: list) -> None:
    cols = [
        sa.Column("sbid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("main_logo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("wikipedia_url", sa.String(length=512), nullable=True),
        sa.Column(
            "external_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", catalogstatus, nullable=False, server_default="approved"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *extras,
        sa.PrimaryKeyConstraint("sbid"),
        sa.UniqueConstraint("slug"),
    ]
    op.create_table(table, *cols)
    op.create_index(f"ix_{table}_name", table, ["name"])
    op.create_index(f"ix_{table}_slug", table, ["slug"])
    op.create_index(f"ix_{table}_status", table, ["status"])


def upgrade() -> None:
    # Concurrent api+worker startups both run alembic; CREATE TYPE is not safe
    # with SQLAlchemy checkfirst under that race. Match earlier migrations.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE catalogstatus AS ENUM ('pending', 'approved', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    for value in EDIT_TYPES:
        op.execute(f"ALTER TYPE edittype ADD VALUE IF NOT EXISTS '{value}'")

    _create_entity(
        "stores",
        [
            sa.Column("founded_year", sa.Integer(), nullable=True),
            sa.Column("store_type", sa.String(length=128), nullable=True),
            sa.Column("headquarters", sa.String(length=255), nullable=True),
            sa.Column("parent_company", sa.String(length=255), nullable=True),
        ],
    )
    _create_entity(
        "services",
        [
            sa.Column("founded_year", sa.Integer(), nullable=True),
            sa.Column("service_type", sa.String(length=128), nullable=True),
            sa.Column("headquarters", sa.String(length=255), nullable=True),
            sa.Column("parent_company", sa.String(length=255), nullable=True),
        ],
    )
    _create_entity(
        "events",
        [
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("start_year", sa.Integer(), nullable=True),
            sa.Column("end_year", sa.Integer(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
        ],
    )
    _create_entity(
        "holidays",
        [
            sa.Column("date_text", sa.String(length=255), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("month", sa.Integer(), nullable=True),
            sa.Column("day", sa.Integer(), nullable=True),
        ],
    )

    for parent, logo, fk, votes, uq in [
        ("stores", "store_logos", "store_id", "store_logo_votes", "uq_store_logo_voter"),
        ("services", "service_logos", "service_id", "service_logo_votes", "uq_service_logo_voter"),
        ("events", "event_logos", "event_id", "event_logo_votes", "uq_event_logo_voter"),
        ("holidays", "holiday_logos", "holiday_id", "holiday_logo_votes", "uq_holiday_logo_voter"),
    ]:
        op.create_table(
            logo,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(fk, postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("image_url", sa.String(length=512), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("month", sa.Integer(), nullable=True),
            sa.Column("event", sa.String(length=255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("edit_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("popularity_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint([fk], [f"{parent}.sbid"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["edit_id"], ["edits.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{logo}_{fk}", logo, [fk])
        op.create_foreign_key(
            f"fk_{parent}_main_logo_id",
            parent,
            logo,
            ["main_logo_id"],
            ["id"],
            ondelete="SET NULL",
        )
        _logo_votes(votes, logo, uq)

    for col, table in [
        ("store_id", "stores"),
        ("service_id", "services"),
        ("event_id", "events"),
        ("holiday_id", "holidays"),
    ]:
        op.add_column(
            "commercials",
            sa.Column(col, postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_commercials_{col}", "commercials", [col])
        op.create_foreign_key(
            f"fk_commercials_{col}",
            "commercials",
            table,
            [col],
            ["sbid"],
        )


def downgrade() -> None:
    for col in ("holiday_id", "event_id", "service_id", "store_id"):
        op.drop_constraint(f"fk_commercials_{col}", "commercials", type_="foreignkey")
        op.drop_index(f"ix_commercials_{col}", table_name="commercials")
        op.drop_column("commercials", col)

    for parent, logo, votes in [
        ("holidays", "holiday_logos", "holiday_logo_votes"),
        ("events", "event_logos", "event_logo_votes"),
        ("services", "service_logos", "service_logo_votes"),
        ("stores", "store_logos", "store_logo_votes"),
    ]:
        op.drop_constraint(f"fk_{parent}_main_logo_id", parent, type_="foreignkey")
        op.drop_table(votes)
        op.drop_table(logo)
        op.drop_table(parent)

    op.execute("DROP TYPE IF EXISTS catalogstatus")
