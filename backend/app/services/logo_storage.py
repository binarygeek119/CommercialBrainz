"""Store and serve transparent PNG brand logos."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from uuid import UUID

from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SAFE_FILENAME = re.compile(r"^[a-f0-9-]{36}\.png$", re.I)
SAFE_LEGACY_FILENAME = re.compile(r"^[a-f0-9-]{36}\.png$", re.I)
SAFE_GALLERY_PATH = re.compile(r"^[a-f0-9-]{36}/[a-f0-9-]{36}\.png$", re.I)


def _upload_root() -> Path:
    root = Path(settings.logo_upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "pending").mkdir(exist_ok=True)
    return root


def _has_transparency(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
        low, high = alpha.getextrema()
        return low < 255
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def process_logo_png(data: bytes) -> bytes:
    """Validate transparent PNG and re-encode at maximum quality."""
    if len(data) > settings.logo_max_bytes:
        raise ValueError(f"Logo too large (max {settings.logo_max_bytes // 1024 // 1024} MB)")
    if len(data) < 68 or not data.startswith(PNG_MAGIC):
        raise ValueError("Logo must be a PNG file")

    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError("Invalid PNG image") from exc

    if img.format != "PNG":
        raise ValueError("Logo must be a PNG file")

    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")
    elif img.mode == "LA":
        img = img.convert("RGBA")
    elif img.mode != "RGBA":
        raise ValueError("Logo must be a transparent PNG (RGBA with alpha channel)")

    if not _has_transparency(img):
        raise ValueError("Logo must include transparency — upload a PNG with a transparent background")

    if img.width < 32 or img.height < 32:
        raise ValueError("Logo must be at least 32×32 pixels")
    if img.width > 4096 or img.height > 4096:
        raise ValueError("Logo must be at most 4096×4096 pixels")

    out = BytesIO()
    img.save(out, format="PNG", compress_level=0, optimize=False)
    return out.getvalue()


def stage_logo(data: bytes) -> tuple[str, str]:
    """Validate, optimize, and stage a logo upload."""
    processed = process_logo_png(data)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.png"
    pending_path = _upload_root() / "pending" / filename
    pending_path.write_bytes(processed)
    return filename, logo_media_url(f"pending/{filename}")


def finalize_staged_logo(staging_file: str, advertiser_sbid: UUID, logo_id: UUID) -> str:
    """Move staged logo into the brand gallery path."""
    if not SAFE_FILENAME.match(staging_file):
        raise ValueError("Invalid staging logo")

    root = _upload_root()
    pending_path = root / "pending" / staging_file
    if not pending_path.is_file():
        raise FileNotFoundError("Staged logo not found")

    brand_dir = root / str(advertiser_sbid)
    brand_dir.mkdir(parents=True, exist_ok=True)
    relative = f"{advertiser_sbid}/{logo_id}.png"
    final_path = brand_dir / f"{logo_id}.png"
    shutil.move(str(pending_path), str(final_path))
    return logo_media_url(relative)


def finalize_staged_logo_legacy(staging_file: str, advertiser_sbid: UUID) -> str:
    """Legacy single-logo path used by older edit_advertiser edits."""
    if not SAFE_FILENAME.match(staging_file):
        raise ValueError("Invalid staging logo")

    root = _upload_root()
    pending_path = root / "pending" / staging_file
    if not pending_path.is_file():
        raise FileNotFoundError("Staged logo not found")

    final_name = f"{advertiser_sbid}.png"
    final_path = root / final_name

    for old in root.glob(f"{advertiser_sbid}.png"):
        if old.is_file():
            old.unlink()

    shutil.move(str(pending_path), str(final_path))
    return logo_media_url(final_name)


def discard_staged_logo(staging_file: str) -> None:
    if not SAFE_FILENAME.match(staging_file):
        return
    path = _upload_root() / "pending" / staging_file
    if path.is_file():
        path.unlink()


def resolve_logo_path(relative: str) -> Path | None:
    relative = relative.strip().lstrip("/")
    if ".." in relative or relative.startswith("/"):
        return None

    root = _upload_root()
    if relative.startswith("pending/"):
        name = relative.removeprefix("pending/")
        if not SAFE_FILENAME.match(name):
            return None
        path = root / "pending" / name
    elif SAFE_GALLERY_PATH.match(relative):
        path = root / relative
    elif SAFE_LEGACY_FILENAME.match(relative):
        path = root / relative
    else:
        return None

    return path if path.is_file() else None


def logo_media_url(relative: str) -> str:
    return f"/api/v1/media/logos/{relative}"
