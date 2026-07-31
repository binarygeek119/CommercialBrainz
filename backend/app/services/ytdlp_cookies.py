"""Admin-managed YouTube cookies file for yt-dlp."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.services.cookie_crypto import (
    CookieEncryptionError,
    cookie_encryption_configured,
    decrypt_cookies,
    encrypt_cookies,
    is_encrypted_blob,
)

logger = logging.getLogger(__name__)

# Keep uploads small; a typical Netscape export is tens of KB.
MAX_COOKIES_BYTES = 2 * 1024 * 1024

_NETSCAPE_HINT = re.compile(r"(?i)netscape|http\s*cookie|#\s*httponly")
_YOUTUBE_HINT = re.compile(r"(?i)youtube\.com|google\.com")


def managed_cookies_path() -> Path:
    """Plaintext path yt-dlp reads (materialized from encrypted storage when needed)."""
    settings = get_settings()
    raw = (settings.ytdlp_cookies_managed_path or "").strip() or "/data/ytdlp/cookies.txt"
    return Path(raw)


def managed_cookies_enc_path() -> Path:
    """Encrypted at-rest path for admin / activated donations."""
    path = managed_cookies_path()
    return path.with_name(path.name + ".enc")


def resolve_cookies_path() -> Path | None:
    """
    First usable cookies file for yt-dlp: env override, then materialized managed file.

    Encrypted storage (*.enc) is decrypted into the managed plaintext path as needed.
    """
    settings = get_settings()
    override = (settings.ytdlp_cookies_file or "").strip()
    if override:
        path = Path(override)
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            pass

    try:
        materialized = materialize_managed_cookies()
        if materialized is not None:
            return materialized
    except CookieEncryptionError as exc:
        logger.warning("Could not materialize managed cookies: %s", exc)
    return None


def cookies_status() -> dict:
    path = managed_cookies_path()
    enc_path = managed_cookies_enc_path()
    active = resolve_cookies_path()
    enc_present = enc_path.is_file() and enc_path.stat().st_size > 0
    plain_present = path.is_file() and path.stat().st_size > 0
    present = enc_present or plain_present
    size = 0
    mtime = None
    source = enc_path if enc_present else path if plain_present else None
    if source is not None and source.is_file():
        size = source.stat().st_size
        mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=UTC).isoformat()
    return {
        "present": present,
        "path": str(path),
        "encrypted_path": str(enc_path),
        "encrypted_at_rest": enc_present,
        "encryption_configured": cookie_encryption_configured(),
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
    # Reject accidental submission of ciphertext as if it were Netscape text.
    if is_encrypted_blob(cleaned):
        raise ValueError("Paste the plaintext Netscape cookies.txt export, not ciphertext")
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


def _atomic_write(path: Path, data: str | bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8")
    os.chmod(tmp, mode)
    tmp.replace(path)


def save_cookies_text(text: str) -> dict:
    """Validate plaintext, encrypt at rest, and materialize a plaintext file for yt-dlp."""
    cleaned = validate_cookies_text(text)
    ciphertext = encrypt_cookies(cleaned)
    enc_path = managed_cookies_enc_path()
    plain_path = managed_cookies_path()
    _atomic_write(enc_path, ciphertext)
    _atomic_write(plain_path, cleaned)
    return cookies_status()


def materialize_managed_cookies() -> Path | None:
    """
    Ensure the managed plaintext cookies.txt exists for yt-dlp.

    Prefers decrypting *.enc; falls back to legacy plaintext managed file.
    """
    enc_path = managed_cookies_enc_path()
    plain_path = managed_cookies_path()

    if enc_path.is_file() and enc_path.stat().st_size > 0:
        blob = enc_path.read_text(encoding="utf-8")
        plain = decrypt_cookies(blob)
        # Refresh plaintext materialization so workers always match ciphertext.
        _atomic_write(plain_path, plain)
        return plain_path

    if plain_path.is_file() and plain_path.stat().st_size > 0:
        return plain_path
    return None


def clear_cookies() -> dict:
    path = managed_cookies_path()
    enc_path = managed_cookies_enc_path()
    for target in (path, enc_path):
        if target.is_file():
            target.unlink()
        tmp = target.with_suffix(target.suffix + ".tmp")
        if tmp.is_file():
            tmp.unlink()
    return cookies_status()


def read_managed_cookies_plaintext() -> str | None:
    """Decrypt/read managed cookies for internal use (never expose via API)."""
    path = materialize_managed_cookies()
    if path is None:
        return None
    return path.read_text(encoding="utf-8")
