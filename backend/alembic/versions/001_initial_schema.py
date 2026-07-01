"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    user_role = postgresql.ENUM("user", "mod", "admin", name="userrole", create_type=True)
    video_visibility = postgresql.ENUM(
        "public", "dmca_hidden", "removed", name="videovisibility", create_type=True
    )
    edit_type = postgresql.ENUM(
        "create_video",
        "edit_video",
        "create_commercial",
        "edit_commercial",
        "merge_commercial",
        "remove_video",
        "add_credit",
        "add_tag",
        name="edittype",
        create_type=True,
    )
    edit_status = postgresql.ENUM(
        "open",
        "applied",
        "rejected",
        "cancelled",
        "failed",
        "automatically_applied",
        name="editstatus",
        create_type=True,
    )
    vote_choice = postgresql.ENUM("yes", "no", "abstain", name="votechoice", create_type=True)
    dmca_status = postgresql.ENUM(
        "submitted",
        "under_review",
        "link_hidden",
        "rejected",
        "restored",
        "permanently_removed",
        name="dmcstatus",
        create_type=True,
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("is_auto_editor", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("accepted_edits_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "advertisers",
        sa.Column("sbid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("external_ids", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agencies",
        sa.Column("sbid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("external_ids", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "commercials",
        sa.Column("sbid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("advertiser_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("advertisers.sbid")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.sbid")),
        sa.Column("year", sa.Integer()),
        sa.Column("campaign_name", sa.String(512)),
        sa.Column("description", sa.Text()),
        sa.Column("external_ids", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "commercial_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("commercial_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commercials.sbid", ondelete="CASCADE")),
        sa.Column("name", sa.String(512), nullable=False),
    )

    op.create_table(
        "videos",
        sa.Column("sbid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("commercial_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commercials.sbid"), nullable=False),
        sa.Column("youtube_id", sa.String(32), unique=True, nullable=False),
        sa.Column("youtube_url", sa.String(512), nullable=False),
        sa.Column("channel_name", sa.String(255)),
        sa.Column("upload_date", sa.Date()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("aspect_ratio", sa.String(16)),
        sa.Column("resolution", sa.String(32)),
        sa.Column("language", sa.String(16)),
        sa.Column("region", sa.String(64)),
        sa.Column("market", sa.String(64)),
        sa.Column("first_aired_date", sa.Date()),
        sa.Column("last_aired_date", sa.Date()),
        sa.Column("network", sa.String(128)),
        sa.Column("transcript", sa.Text()),
        sa.Column("slogan", sa.String(512)),
        sa.Column("cta_text", sa.String(512)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("visibility", video_visibility, server_default="public"),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "video_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.sbid", ondelete="CASCADE")),
        sa.Column("role", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )

    op.create_table(
        "video_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.sbid", ondelete="CASCADE")),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.UniqueConstraint("video_id", "tag", name="uq_video_tag"),
    )

    op.create_table(
        "airings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.sbid", ondelete="CASCADE")),
        sa.Column("aired_date", sa.Date()),
        sa.Column("network", sa.String(128)),
        sa.Column("market", sa.String(64)),
        sa.Column("region", sa.String(64)),
    )

    op.create_table(
        "edits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edit_type", edit_type, nullable=False),
        sa.Column("status", edit_status, server_default="open"),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("before_state", postgresql.JSONB()),
        sa.Column("after_state", postgresql.JSONB(), nullable=False),
        sa.Column("editor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edits.id", ondelete="CASCADE")),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("choice", vote_choice, nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("edit_id", "voter_id", name="uq_edit_voter"),
    )

    op.create_table(
        "dmca_takedowns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.sbid")),
        sa.Column("status", dmca_status, server_default="submitted"),
        sa.Column("claimant_name", sa.String(255), nullable=False),
        sa.Column("claimant_email", sa.String(255), nullable=False),
        sa.Column("claimant_address", sa.Text()),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("signature", sa.String(255), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("review_notes", sa.Text()),
        sa.Column("counter_claim_text", sa.Text()),
        sa.Column("counter_claimant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("details", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "audit_logs",
        "dmca_takedowns",
        "votes",
        "edits",
        "airings",
        "video_tags",
        "video_credits",
        "videos",
        "commercial_products",
        "commercials",
        "agencies",
        "advertisers",
        "users",
    ]:
        op.drop_table(table)
    for enum in ["dmcstatus", "votechoice", "editstatus", "edittype", "videovisibility", "userrole"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
