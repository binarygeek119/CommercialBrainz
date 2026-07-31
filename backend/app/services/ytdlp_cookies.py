"""Admin-managed YouTube cookies file for yt-dlp."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
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

# Auth-ish cookie names that matter for yt-dlp YouTube access.
_AUTH_COOKIE_NAMES = frozenset(
    {
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        "__Secure-1PAPISID",
        "__Secure-3PAPISID",
        "LOGIN_INFO",
        "SIDCC",
        "__Secure-1PSIDTS",
        "__Secure-3PSIDTS",
    }
)

# Public video used only to probe whether cookies still work with yt-dlp.
_VALIDATE_VIDEO_ID = "jNQXAC9IVRw"  # "Me at the zoo" — stable short public clip
_VALIDATE_TIMEOUT_SEC = 90


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


def _parse_netscape_rows(text: str) -> list[dict]:
    """Parse Netscape cookies.txt rows (domain, flag, path, secure, expires, name, value)."""
    rows: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        http_only = False
        if line.startswith("#HttpOnly_") or line.startswith("#httponly_"):
            http_only = True
            line = line.split("_", 1)[1]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, secure, expires_s, name, value = parts[:7]
        try:
            expires = int(expires_s)
        except ValueError:
            expires = 0
        rows.append(
            {
                "domain": domain.strip(),
                "path": path.strip(),
                "secure": secure.upper() == "TRUE",
                "expires": expires,
                "name": name.strip(),
                "value": value,
                "http_only": http_only,
            }
        )
    return rows


def _is_youtube_related(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return (
        d.endswith("youtube.com")
        or d.endswith("google.com")
        or d == "youtube.com"
        or d == "google.com"
    )


def analyze_cookies_file(path: Path | None = None) -> dict:
    """
    Inspect cookie expiry without exposing values.

    Returns fields describing whether key YouTube/Google auth cookies look expired.
    Session cookies (expires=0) are treated as unknown lifetime.
    """
    target = path or resolve_cookies_path()
    result: dict = {
        "expiry_known": False,
        "expired": False,
        "expires_at": None,
        "expires_in_seconds": None,
        "auth_cookie_count": 0,
        "session_cookie_count": 0,
        "needs_refresh": False,
        "refresh_reason": None,
    }
    if target is None or not target.is_file():
        result["needs_refresh"] = True
        result["refresh_reason"] = "No cookies file is active"
        return result

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result["needs_refresh"] = True
        result["refresh_reason"] = f"Could not read cookies file: {exc}"
        return result

    rows = [r for r in _parse_netscape_rows(text) if _is_youtube_related(r["domain"])]
    auth_rows = [r for r in rows if r["name"] in _AUTH_COOKIE_NAMES]
    result["auth_cookie_count"] = len(auth_rows)

    if not auth_rows:
        # File may still help for mild bot checks, but login cookies are missing.
        result["needs_refresh"] = True
        result["refresh_reason"] = "No YouTube/Google auth cookies found in the file"
        return result

    now = datetime.now(UTC)
    now_ts = int(now.timestamp())
    lasting = [r for r in auth_rows if r["expires"] > 0]
    session = [r for r in auth_rows if r["expires"] <= 0]
    result["session_cookie_count"] = len(session)

    if lasting:
        # Cookie jar is only as good as the soonest-expiring auth cookie.
        soonest = min(r["expires"] for r in lasting)
        result["expiry_known"] = True
        result["expires_at"] = datetime.fromtimestamp(soonest, tz=UTC).isoformat()
        result["expires_in_seconds"] = soonest - now_ts
        if soonest <= now_ts:
            result["expired"] = True
            result["needs_refresh"] = True
            result["refresh_reason"] = "One or more auth cookies have expired"
        elif soonest - now_ts <= int(timedelta(days=3).total_seconds()):
            result["needs_refresh"] = True
            result["refresh_reason"] = "Auth cookies expire within 3 days — re-export soon"
    elif session:
        result["refresh_reason"] = (
            "Only session cookies present (no expiry). Validity unknown until live check."
        )
    return result


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
    analysis = analyze_cookies_file(active)
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
        **analysis,
        "last_validated_at": None,
        "last_validation_ok": None,
        "last_validation_error": None,
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


def probe_cookies_live(*, youtube_id: str = _VALIDATE_VIDEO_ID) -> dict:
    """
    Run a lightweight yt-dlp metadata probe to see if active cookies still work.

    Does not download media. Returns status plus validation fields.
    """
    from app.services.ytdlp_auth import ytdlp_common_args, ytdlp_error_message

    status = cookies_status()
    active = resolve_cookies_path()
    if active is None and not status.get("browser_fallback"):
        status["last_validated_at"] = datetime.now(UTC).isoformat()
        status["last_validation_ok"] = False
        status["last_validation_error"] = "No cookies file is active"
        status["needs_refresh"] = True
        status["refresh_reason"] = status["last_validation_error"]
        return status

    url = f"https://www.youtube.com/watch?v={youtube_id}"
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--no-playlist",
        "--skip-download",
        "--no-warnings",
        "-J",
        "--",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_VALIDATE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        status["last_validated_at"] = datetime.now(UTC).isoformat()
        status["last_validation_ok"] = False
        status["last_validation_error"] = "Validation timed out talking to YouTube"
        status["needs_refresh"] = True
        status["refresh_reason"] = status["last_validation_error"]
        return status
    except OSError as exc:
        status["last_validated_at"] = datetime.now(UTC).isoformat()
        status["last_validation_ok"] = False
        status["last_validation_error"] = f"Could not run yt-dlp: {exc}"
        return status

    status["last_validated_at"] = datetime.now(UTC).isoformat()
    if result.returncode != 0:
        err = ytdlp_error_message(result.stderr or result.stdout or "yt-dlp failed")
        status["last_validation_ok"] = False
        status["last_validation_error"] = err[:500]
        lowered = err.lower()
        if "sign in" in lowered or "bot" in lowered or "cookies" in lowered:
            status["needs_refresh"] = True
            status["refresh_reason"] = (
                "Live check failed — re-export cookies from a logged-in browser"
            )
        return status

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        status["last_validation_ok"] = False
        status["last_validation_error"] = "yt-dlp returned non-JSON output"
        return status

    if not payload.get("id") and not payload.get("title"):
        status["last_validation_ok"] = False
        status["last_validation_error"] = "yt-dlp returned empty metadata"
        status["needs_refresh"] = True
        status["refresh_reason"] = status["last_validation_error"]
        return status

    status["last_validation_ok"] = True
    status["last_validation_error"] = None
    # Live check succeeded; only keep expiry-based refresh hints from analysis.
    if status.get("expired"):
        status["needs_refresh"] = True
        status["refresh_reason"] = (
            "Live check passed, but auth cookie timestamps are expired — re-export"
        )
    elif status.get("needs_refresh") and status.get("refresh_reason", "").startswith(
        "Auth cookies expire within"
    ):
        pass  # keep the "expires soon" hint
    else:
        status["needs_refresh"] = False
        status["refresh_reason"] = None
    logger.info("YouTube cookies live validation succeeded for %s", youtube_id)
    return status
