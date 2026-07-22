"""Shared yt-dlp CLI auth helpers (YouTube cookies, JS runtime, extractor args)."""

from __future__ import annotations

import shutil

from app.config import get_settings
from app.services.ytdlp_cookies import resolve_cookies_path

_BOT_MARKERS = (
    "sign in to confirm you’re not a bot",
    "sign in to confirm you're not a bot",
    "confirm your age",
    "login required",
)

_FORMAT_MARKERS = (
    "requested format is not available",
    "format is not available",
    "only images are available",
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


def ytdlp_js_runtime_args() -> list[str]:
    """Enable an available JS runtime so yt-dlp can solve YouTube challenges."""
    for name in ("node", "deno"):
        if shutil.which(name):
            return ["--js-runtimes", name]
    return []


def ytdlp_extractor_arg_list(extractor_args: str | None = None) -> list[str]:
    """Build --extractor-args from an override or settings (omit when empty)."""
    if extractor_args is None:
        extractor_args = get_settings().ytdlp_extractor_args
    value = (extractor_args or "").strip()
    if not value:
        return []
    return ["--extractor-args", value]


def ytdlp_common_args(*, extractor_args: str | None = None) -> list[str]:
    """Auth + JS runtime + extractor args shared by metadata and download calls."""
    return [
        *ytdlp_auth_args(),
        *ytdlp_js_runtime_args(),
        *ytdlp_extractor_arg_list(extractor_args),
    ]


def ytdlp_error_message(stderr_or_stdout: str, *, fallback: str = "yt-dlp failed") -> str:
    """Trim yt-dlp stderr and hint at cookie / JS / format config when relevant."""
    msg = (stderr_or_stdout or fallback).strip() or fallback
    lowered = msg.lower()
    hint = ""
    if any(marker in lowered for marker in _BOT_MARKERS):
        hint = (
            " YouTube blocked this request (bot check). "
            "An admin can paste a Netscape cookies.txt under Admin → YouTube cookies "
            "(or set YTDLP_COOKIES_FILE). See yt-dlp wiki: Exporting YouTube cookies."
        )
    elif any(marker in lowered for marker in _FORMAT_MARKERS):
        hint = (
            " No matching stream formats (often missing JS runtime or cookies, "
            "or YouTube blocked this IP’s player clients). "
            "Ensure the API image has Node.js, cookies are set under Admin → YouTube cookies, "
            "and try YTDLP_EXTRACTOR_ARGS / YTDLP_FORMAT if needed."
        )
    if not hint:
        return msg[:500]
    budget = 500 - len(hint)
    if budget < 80:
        return hint.strip()
    return f"{msg[:budget].rstrip()}{hint}"
