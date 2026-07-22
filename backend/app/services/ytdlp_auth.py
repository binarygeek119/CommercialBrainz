"""Shared yt-dlp CLI auth helpers (YouTube cookies)."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings

_BOT_MARKERS = (
    "sign in to confirm you’re not a bot",
    "sign in to confirm you're not a bot",
    "confirm your age",
    "login required",
)


def ytdlp_auth_args() -> list[str]:
    """Optional cookie args for yt-dlp. Prefer cookies file over browser profile."""
    settings = get_settings()
    cookies_file = (settings.ytdlp_cookies_file or "").strip()
    if cookies_file:
        path = Path(cookies_file)
        if path.is_file():
            return ["--cookies", str(path)]
        # Still pass the path so yt-dlp's error is clear if misconfigured.
        return ["--cookies", cookies_file]

    browser = (settings.ytdlp_cookies_from_browser or "").strip()
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
            "Set YTDLP_COOKIES_FILE to a Netscape cookies.txt exported from a logged-in browser "
            "(see yt-dlp wiki: Exporting YouTube cookies), then restart api/worker."
        )
        # Keep under API detail limits used elsewhere (~500 chars).
        budget = 500 - len(hint)
        if budget < 80:
            return hint.strip()
        return f"{msg[:budget].rstrip()}{hint}"
    return msg[:500]
