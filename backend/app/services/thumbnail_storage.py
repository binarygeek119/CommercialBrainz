"""Store and serve user-uploaded video thumbnails."""

from __future__ import annotations

import imghdr
import logging
import re
import shutil
import uuid
from pathlib import Path
from uuid import UUID

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
EXTENSION_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
SAFE_FILENAME = re.compile(r"^[a-f0-9-]{36}\.(jpg|jpeg|png|webp)$", re.I)
SAFE_VIDEO_FILENAME = re.compile(
    r"^[a-f0-9-]{36}\.(jpg|jpeg|png|webp)$", re.I
)


def _upload_root() -> Path:
    root = Path(settings.thumbnail_upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "pending").mkdir(exist_ok=True)
    return root


def _detect_image_type(data: bytes) -> str | None:
    kind = imghdr.what(None, h=data[:32])
    if kind == "jpeg":
        return "image/jpeg"
    if kind == "png":
        return "image/png"
    if kind == "webp":
        return "image/webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_thumbnail_bytes(data: bytes, declared_type: str | None = None) -> str:
    if len(data) > settings.thumbnail_max_bytes:
        raise ValueError(f"Image too large (max {settings.thumbnail_max_bytes // 1024 // 1024} MB)")
    if len(data) < 64:
        raise ValueError("Image file is too small")

    detected = _detect_image_type(data)
    if not detected or detected not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Upload a JPEG, PNG, or WebP image")

    if declared_type and declared_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Upload a JPEG, PNG, or WebP image")

    return detected


def stage_thumbnail(data: bytes, content_type: str | None = None) -> tuple[str, str]:
    """Save upload to pending storage. Returns (staging_file, public_url)."""
    image_type = validate_thumbnail_bytes(data, content_type)
    ext = EXTENSION_BY_TYPE[image_type]
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    pending_path = _upload_root() / "pending" / filename
    pending_path.write_bytes(data)

    public_url = thumbnail_media_url(f"pending/{filename}")
    return filename, public_url


def finalize_staged_thumbnail(staging_file: str, video_sbid: UUID) -> str:
    """Move pending thumbnail to the video's permanent file."""
    if not SAFE_FILENAME.match(staging_file):
        raise ValueError("Invalid staging thumbnail")

    root = _upload_root()
    pending_path = root / "pending" / staging_file
    if not pending_path.is_file():
        raise FileNotFoundError("Staged thumbnail not found")

    ext = pending_path.suffix.lower()
    final_name = f"{video_sbid}{ext}"
    final_path = root / final_name

    for old in root.glob(f"{video_sbid}.*"):
        if old.is_file():
            old.unlink()

    shutil.move(str(pending_path), str(final_path))
    return thumbnail_media_url(final_name)


def discard_staged_thumbnail(staging_file: str) -> None:
    if not SAFE_FILENAME.match(staging_file):
        return
    path = _upload_root() / "pending" / staging_file
    if path.is_file():
        path.unlink()


def resolve_media_path(relative: str) -> Path | None:
    """Resolve a safe relative path under the upload root."""
    relative = relative.strip().lstrip("/")
    if ".." in relative or relative.startswith("/"):
        return None

    root = _upload_root()
    if relative.startswith("pending/"):
        name = relative.removeprefix("pending/")
        if not SAFE_FILENAME.match(name):
            return None
        path = root / "pending" / name
    else:
        name = relative
        if not SAFE_VIDEO_FILENAME.match(name):
            return None
        path = root / name

    return path if path.is_file() else None


def thumbnail_media_url(relative: str) -> str:
    return f"/api/v1/media/thumbnails/{relative}"


def is_hosted_thumbnail(url: str | None) -> bool:
    if not url:
        return False
    return "/api/v1/media/thumbnails/" in url
