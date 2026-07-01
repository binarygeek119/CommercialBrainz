"""Media fingerprints for phash, file hash, and audio fingerprint

Revision ID: 004
Revises: 003
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    fingerprint_phase = postgresql.ENUM("preview", "final", name="fingerprintphase", create_type=True)
    fingerprint_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed", name="fingerprintstatus", create_type=True
    )
    hash_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed", name="videohashstatus", create_type=True
    )
    hash_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "media_fingerprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edits.id"), nullable=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.sbid"), nullable=True),
        sa.Column("youtube_id", sa.String(32), nullable=False, index=True),
        sa.Column("phase", fingerprint_phase, nullable=False),
        sa.Column("status", fingerprint_status, nullable=False, server_default="pending"),
        sa.Column("phash", sa.BigInteger(), nullable=True),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("audio_fingerprint", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_media_fingerprints_status_created",
        "media_fingerprints",
        ["status", "created_at"],
    )
    op.create_index("ix_media_fingerprints_edit_id", "media_fingerprints", ["edit_id"])

    op.add_column("videos", sa.Column("phash", sa.BigInteger(), nullable=True))
    op.add_column("videos", sa.Column("file_sha256", sa.String(64), nullable=True))
    op.add_column("videos", sa.Column("audio_fingerprint", sa.Text(), nullable=True))
    op.add_column(
        "videos",
        sa.Column("hash_status", hash_status, nullable=False, server_default="pending"),
    )
    op.add_column("videos", sa.Column("hashed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_videos_phash", "videos", ["phash"])


def downgrade() -> None:
    op.drop_index("ix_videos_phash", table_name="videos")
    op.drop_column("videos", "hashed_at")
    op.drop_column("videos", "hash_status")
    op.drop_column("videos", "audio_fingerprint")
    op.drop_column("videos", "file_sha256")
    op.drop_column("videos", "phash")

    op.drop_index("ix_media_fingerprints_edit_id", table_name="media_fingerprints")
    op.drop_index("ix_media_fingerprints_status_created", table_name="media_fingerprints")
    op.drop_table("media_fingerprints")

    op.execute("DROP TYPE IF EXISTS videohashstatus")
    op.execute("DROP TYPE IF EXISTS fingerprintstatus")
    op.execute("DROP TYPE IF EXISTS fingerprintphase")
