"""Admin-managed YouTube cookies file for yt-dlp."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings

# Keep uploads small; a typical Netscape export is tens of KB.
MAX_COOKIES_BYTES = 2 * 1024 * 1024

_NETSCAPE_HINT = re.compile(r"(?i)netscape|http\s*cookie|#\s*httponly")
_YOUTUBE_HINT = re.compile(r"(?i)youtube\.com|google\.com")


def managed_cookies_path() -> Path:
    """Canonical path admins write; workers/api both read this file."""
    settings = get_settings()
    raw = (settings.ytdlp_cookies_managed_path or "").strip() or "/data/ytdlp/cookies.txt"
    return Path(raw)


def resolve_cookies_path() -> Path | None:
    """First existing cookies file: env override, then managed admin path."""
    settings = get_settings()
    candidates: list[Path] = []
    override = (settings.ytdlp_cookies_file or "").strip()
    if override:
        candidates.append(Path(override))
    managed = managed_cookies_path()
    if not candidates or managed != candidates[0]:
        candidates.append(managed)
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def cookies_status() -> dict:
    path = managed_cookies_path()
    active = resolve_cookies_path()
    present = path.is_file() and path.stat().st_size > 0
    size = path.stat().st_size if path.is_file() else 0
    mtime = None
    if path.is_file():
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return {
        "present": present,
        "path": str(path),
        "size_bytes": size if present else 0,
        "updated_at": mtime if present else None,
        "active": active is not None,
        "active_path": str(active) if active else None,
        "env_override": bool((get_settings().ytdlp_cookies_file or "").strip()),
        "browser_fallback": bool((get_settings().ytdlp_cookies_from_browser or "").strip()),
    }


def validate_cookies_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise ValueError("Cookies content is empty")
    encoded = cleaned.encode("utf-8")
    if len(encoded) > MAX_COOKIES_BYTES:
        raise ValueError(f"Cookies file too large (max {MAX_COOKIES_BYTES // 1024} KiB)")
    if not (
        _NETSCAPE_HINT.search(cleaned)
        or _YOUTUBE_HINT.search(cleaned)
        or "\t" in cleaned
    ):
        raise ValueError(
            "Does not look like a Netscape cookies.txt export. "
            "Export from a logged-in browser (yt-dlp wiki: Exporting YouTube cookies)."
        )
    return cleaned + "\n"


def save_cookies_text(text: str) -> dict:
    cleaned = validate_cookies_text(text)
    path = managed_cookies_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(cleaned, encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return cookies_status()


def clear_cookies() -> dict:
    path = managed_cookies_path()
    if path.is_file():
        path.unlink()
    # Best-effort cleanup of a leftover temp file.
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.is_file():
        tmp.unlink()
    return cookies_status()
