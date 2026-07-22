"""Index videos.file_sha256 for exact hash lookups.

Revision ID: 026
Revises: 025
"""

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_videos_file_sha256",
        "videos",
        ["file_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_videos_file_sha256", table_name="videos")
