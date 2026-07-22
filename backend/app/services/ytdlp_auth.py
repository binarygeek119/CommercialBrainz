"""Shared yt-dlp CLI auth helpers (YouTube cookies)."""

from __future__ import annotations

from app.config import get_settings
from app.services.ytdlp_cookies import resolve_cookies_path

_BOT_MARKERS = (
    "sign in to confirm you’re not a bot",
    "sign in to confirm you're not a bot",
    "confirm your age",
    "login required",
)


def ytdlp_auth_args() -> list[str]:
    """Optional cookie args for yt-dlp. Prefer cookies file over browser profile."""
    path = resolve_cookies_path()
    if path is not None:
        return ["--cookies", str(path)]

    browser = (get_settings().ytdlp_cookies_from_browser or "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def ytdlp_error_message(stderr_or_stdout: str, *, fallback: str = "yt-dlp failed") -> str:
    """Trim yt-dlp stderr and hint at cookie config for bot / login blocks."""
    msg = (stderr_or_stdout or fallback).strip() or fallback
    lowered = msg.lower()
    if any(marker in lowered for marker in _BOT_MARKERS):
        hint = (
            " YouTube blocked this request (bot check). "
            "An admin can paste a Netscape cookies.txt under Admin → YouTube cookies "
            "(or set YTDLP_COOKIES_FILE). See yt-dlp wiki: Exporting YouTube cookies."
        )
        budget = 500 - len(hint)
        if budget < 80:
            return hint.strip()
        return f"{msg[:budget].rstrip()}{hint}"
    return msg[:500]
