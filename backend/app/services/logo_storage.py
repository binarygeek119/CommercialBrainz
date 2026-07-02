"""Store and serve transparent PNG and SVG brand logos."""

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
LOGO_EXTENSIONS = (".png", ".svg")
SAFE_FILENAME = re.compile(r"^[a-f0-9-]{36}\.(?:png|svg)$", re.I)
SAFE_LEGACY_FILENAME = re.compile(r"^[a-f0-9-]{36}\.(?:png|svg)$", re.I)
SAFE_GALLERY_PATH = re.compile(r"^[a-f0-9-]{36}/[a-f0-9-]{36}\.(?:png|svg)$", re.I)
_SVG_SCRIPT = re.compile(r"<script[\s>].*?</script>", re.I | re.S)
_SVG_FOREIGN_OBJECT = re.compile(r"<foreignObject[\s>].*?</foreignObject>", re.I | re.S)
_SVG_EVENT_HANDLER = re.compile(r'\s(on\w+)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.I)
_SVG_JS_URL = re.compile(
    r'(\s(?:href|xlink:href)\s*=\s*["\'])javascript:[^"\']*(["\'])',
    re.I,
)


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


def _detect_logo_extension(data: bytes) -> str:
    if data.startswith(PNG_MAGIC):
        return ".png"

    stripped = data.lstrip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:]

    head = stripped[:4096].lower()
    if stripped[:5].lower() == b"<?xml" or stripped[:4].lower() == b"<svg" or b"<svg" in head:
        return ".svg"

    raise ValueError("Logo must be a PNG or SVG file")


def _sanitize_svg(text: str) -> str:
    text = _SVG_SCRIPT.sub("", text)
    text = _SVG_FOREIGN_OBJECT.sub("", text)
    text = _SVG_EVENT_HANDLER.sub("", text)
    text = _SVG_JS_URL.sub(r"\1#\2", text)
    return text.strip()


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


def process_logo_svg(data: bytes) -> bytes:
    """Validate SVG and strip unsafe markup before storage."""
    if len(data) > settings.logo_max_bytes:
        raise ValueError(f"Logo too large (max {settings.logo_max_bytes // 1024 // 1024} MB)")
    if len(data) < 16:
        raise ValueError("Logo must be an SVG file")

    stripped = data.lstrip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:]

    try:
        text = stripped.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid SVG file") from exc

    if "<svg" not in text.lower():
        raise ValueError("Logo must be an SVG file")

    sanitized = _sanitize_svg(text)
    if "<svg" not in sanitized.lower():
        raise ValueError("Invalid SVG file")

    return sanitized.encode("utf-8")


def process_logo(data: bytes) -> tuple[bytes, str]:
    """Validate and normalize a PNG or SVG logo upload."""
    ext = _detect_logo_extension(data)
    if ext == ".png":
        return process_logo_png(data), ext
    return process_logo_svg(data), ext


def stage_logo(data: bytes) -> tuple[str, str]:
    """Validate, optimize, and stage a logo upload."""
    processed, ext = process_logo(data)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    pending_path = _upload_root() / "pending" / filename
    pending_path.write_bytes(processed)
    return filename, logo_media_url(f"pending/{filename}")


def _staging_extension(staging_file: str) -> str:
    ext = Path(staging_file).suffix.lower()
    if ext not in LOGO_EXTENSIONS:
        raise ValueError("Invalid staging logo")
    return ext


def finalize_staged_logo(staging_file: str, advertiser_sbid: UUID, logo_id: UUID) -> str:
    """Move staged logo into the brand gallery path."""
    if not SAFE_FILENAME.match(staging_file):
        raise ValueError("Invalid staging logo")

    root = _upload_root()
    pending_path = root / "pending" / staging_file
    if not pending_path.is_file():
        raise FileNotFoundError("Staged logo not found")

    ext = _staging_extension(staging_file)
    brand_dir = root / str(advertiser_sbid)
    brand_dir.mkdir(parents=True, exist_ok=True)
    relative = f"{advertiser_sbid}/{logo_id}{ext}"
    final_path = brand_dir / f"{logo_id}{ext}"
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

    ext = _staging_extension(staging_file)
    final_name = f"{advertiser_sbid}{ext}"
    final_path = root / final_name

    for old in root.glob(f"{advertiser_sbid}.*"):
        if old.is_file() and old.suffix.lower() in LOGO_EXTENSIONS:
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


def logo_media_type(path: Path) -> str:
    if path.suffix.lower() == ".svg":
        return "image/svg+xml"
    return "image/png"


def logo_media_url(relative: str) -> str:
    return f"/api/v1/media/logos/{relative}"
