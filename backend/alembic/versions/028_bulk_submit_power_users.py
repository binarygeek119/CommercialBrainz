"""Bulk submit / power users: flags, staging tables, terms, commercial provenance.

Revision ID: 028
Revises: 027
"""

# ruff: noqa: E501

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None

_BATCH_STATUS = postgresql.ENUM(
    "importing",
    "ready",
    "failed",
    name="bulksubmissionbatchstatus",
    create_type=False,
)
_ITEM_STATUS = postgresql.ENUM(
    "pending_meta",
    "hashing",
    "ready",
    "submitted",
    "skipped",
    "failed",
    "duplicate",
    name="bulksubmissionitemstatus",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE bulksubmissionbatchstatus AS ENUM
                ('importing', 'ready', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE bulksubmissionitemstatus AS ENUM
                ('pending_meta', 'hashing', 'ready', 'submitted',
                 'skipped', 'failed', 'duplicate');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.add_column(
        "users",
        sa.Column("bulk_submit_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("power_user_terms_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("power_user_terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("bulk_submit_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("bulk_submit_revoke_reason", sa.Text(), nullable=True),
    )

    op.add_column(
        "commercials",
        sa.Column("was_bulk_imported", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "power_user_terms_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_power_user_terms_documents_version",
        "power_user_terms_documents",
        ["version"],
        unique=True,
    )
    op.create_index(
        "ix_power_user_terms_documents_is_active",
        "power_user_terms_documents",
        ["is_active"],
    )

    op.create_table(
        "bulk_submission_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("playlist_url", sa.String(1024), nullable=False),
        sa.Column("playlist_id", sa.String(128), nullable=True),
        sa.Column("playlist_title", sa.String(512), nullable=True),
        sa.Column("status", _BATCH_STATUS, nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_bulk_submission_batches_owner_id",
        "bulk_submission_batches",
        ["owner_id"],
    )
    op.create_index("ix_bulk_submission_batches_status", "bulk_submission_batches", ["status"])

    op.create_table(
        "bulk_submission_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bulk_submission_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("youtube_id", sa.String(32), nullable=False),
        sa.Column("youtube_url", sa.String(512), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", _ITEM_STATUS, nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "fingerprint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_fingerprints.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "edit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("edits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_bulk_submission_items_batch_id", "bulk_submission_items", ["batch_id"])
    op.create_index("ix_bulk_submission_items_owner_id", "bulk_submission_items", ["owner_id"])
    op.create_index("ix_bulk_submission_items_youtube_id", "bulk_submission_items", ["youtube_id"])
    op.create_index("ix_bulk_submission_items_status", "bulk_submission_items", ["status"])
    op.create_index(
        "ix_bulk_submission_items_fingerprint_id",
        "bulk_submission_items",
        ["fingerprint_id"],
    )

    from app.data.power_user_terms_v1 import POWER_USER_TERMS_V1

    sections_json = json.dumps(POWER_USER_TERMS_V1["sections"])
    op.execute(
        sa.text(
            """
            INSERT INTO power_user_terms_documents (id, version, title, intro, sections, is_active)
            VALUES (gen_random_uuid(), :version, :title, :intro, CAST(:sections AS jsonb), true)
            """
        ).bindparams(
            version=POWER_USER_TERMS_V1["version"],
            title=POWER_USER_TERMS_V1["title"],
            intro=POWER_USER_TERMS_V1["intro"],
            sections=sections_json,
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM power_user_terms_documents WHERE version = 1"))
    op.drop_table("bulk_submission_items")
    op.drop_table("bulk_submission_batches")
    op.drop_index(
        "ix_power_user_terms_documents_is_active",
        table_name="power_user_terms_documents",
    )
    op.drop_index("ix_power_user_terms_documents_version", table_name="power_user_terms_documents")
    op.drop_table("power_user_terms_documents")
    op.drop_column("commercials", "was_bulk_imported")
    op.drop_column("users", "bulk_submit_revoke_reason")
    op.drop_column("users", "bulk_submit_revoked_at")
    op.drop_column("users", "power_user_terms_accepted_at")
    op.drop_column("users", "power_user_terms_version")
    op.drop_column("users", "bulk_submit_enabled")
    op.execute("DROP TYPE IF EXISTS bulksubmissionitemstatus")
    op.execute("DROP TYPE IF EXISTS bulksubmissionbatchstatus")
