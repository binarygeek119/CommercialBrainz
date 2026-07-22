"""Fetch YouTube video metadata for submission pre-fill (yt-dlp, no download)."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from math import gcd
from typing import Any
from urllib.request import Request, urlopen

from app.services.ytdlp_auth import ytdlp_common_args, ytdlp_error_message
from app.utils import (
    extract_youtube_id,
    extract_youtube_playlist_id,
    youtube_playlist_url,
    youtube_watch_url,
)

logger = logging.getLogger(__name__)

_VTT_TIMESTAMP = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*$"
)


def _canonical_youtube_url(value: str) -> str:
    youtube_id = extract_youtube_id((value or "").strip())
    return youtube_watch_url(youtube_id)


def _canonical_youtube_playlist_url(value: str) -> str:
    playlist_id = extract_youtube_playlist_id((value or "").strip())
    return youtube_playlist_url(playlist_id)


def _run_ytdlp_json(url: str) -> dict[str, Any]:
    safe_url = _canonical_youtube_url(url)
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        safe_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=45)
    if result.returncode != 0:
        raise RuntimeError(ytdlp_error_message(result.stderr or result.stdout))
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid metadata response from YouTube") from exc


def _run_ytdlp_playlist_flat(url: str) -> dict[str, Any]:
    """Dump playlist JSON (flat entries) without downloading media."""
    safe_url = _canonical_youtube_playlist_url(url)
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--flat-playlist",
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        safe_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    if result.returncode != 0:
        raw = result.stderr or result.stdout or "yt-dlp playlist failed"
        raise RuntimeError(ytdlp_error_message(raw))
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid playlist response from YouTube") from exc


def expand_youtube_playlist(url: str, *, max_items: int) -> dict[str, Any]:
    """
    Expand a YouTube playlist URL into ordered video entries.

    Returns dict with playlist_id, playlist_title, and entries:
    [{youtube_id, youtube_url, title, position}, ...]
    """
    info = _run_ytdlp_playlist_flat(url)
    entries_raw = info.get("entries") or []
    if not entries_raw and info.get("id") and info.get("_type") != "playlist":
        # Single video mistaken for playlist — treat as one entry.
        youtube_id = info.get("id")
        from app.utils import youtube_watch_url

        return {
            "playlist_id": None,
            "playlist_title": info.get("title"),
            "entries": [
                {
                    "youtube_id": youtube_id,
                    "youtube_url": youtube_watch_url(youtube_id),
                    "title": info.get("title"),
                    "position": 0,
                }
            ],
        }

    from app.utils import youtube_watch_url

    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries_raw):
        if not entry:
            continue
        youtube_id = entry.get("id") or entry.get("url")
        if not youtube_id or not isinstance(youtube_id, str):
            continue
        # Flat playlist sometimes returns watch URLs; normalize to 11-char id when possible.
        try:
            from app.utils import extract_youtube_id

            youtube_id = extract_youtube_id(youtube_id)
        except ValueError:
            if len(youtube_id) != 11:
                continue
        entries.append(
            {
                "youtube_id": youtube_id,
                "youtube_url": youtube_watch_url(youtube_id),
                "title": (entry.get("title") or "").strip() or None,
                "position": index,
            }
        )
        if len(entries) >= max_items:
            break

    if not entries:
        raise RuntimeError("Playlist has no videos or could not be read")

    return {
        "playlist_id": info.get("id") or info.get("playlist_id"),
        "playlist_title": info.get("title") or info.get("playlist_title"),
        "entries": entries,
    }


def _aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _format_upload_date(raw: str | None) -> str | None:
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def _pick_language(info: dict[str, Any]) -> str | None:
    lang = info.get("language")
    if isinstance(lang, str) and lang.strip():
        return lang.strip().split("-")[0].lower()
    for key in ("en", "en-US", "en-GB"):
        subs = info.get("subtitles") or {}
        auto = info.get("automatic_captions") or {}
        if key in subs or key in auto:
            return "en"
    return None


def _subtitle_tracks(info: dict[str, Any], lang: str = "en") -> list[dict[str, Any]]:
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    for key in (lang, f"{lang}-US", f"{lang}-GB"):
        if key in subs:
            return subs[key]
        if key in auto:
            return auto[key]
    if subs:
        return next(iter(subs.values()))
    if auto:
        return next(iter(auto.values()))
    return []


def _parse_vtt(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT":
            continue
        if stripped.isdigit():
            continue
        if _VTT_TIMESTAMP.match(stripped):
            continue
        if stripped.startswith("NOTE") or stripped.startswith("STYLE"):
            continue
        if re.match(r"^<[^>]+>$", stripped):
            continue
        cleaned = re.sub(r"<[^>]+>", "", stripped).strip()
        if cleaned:
            lines.append(cleaned)
    # De-dupe consecutive identical caption lines (common in auto-captions).
    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return "\n".join(deduped).strip()


def _fetch_subtitle_text(info: dict[str, Any], lang: str = "en") -> str | None:
    tracks = _subtitle_tracks(info, lang)
    if not tracks:
        return None
    preferred = next(
        (t for t in tracks if t.get("ext") in ("vtt", "srv3", "json3")),
        tracks[0],
    )
    url = preferred.get("url")
    if not url:
        return None
    try:
        req = Request(url, headers={"User-Agent": "CommercialBrainz/1.0"})
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.debug("Subtitle fetch failed for %s", info.get("id"), exc_info=True)
        return None
    if preferred.get("ext") == "json3" or body.lstrip().startswith("{"):
        try:
            data = json.loads(body)
            events = data.get("events") or []
            parts: list[str] = []
            for event in events:
                for seg in event.get("segs") or []:
                    text = (seg.get("utf8") or "").strip()
                    if text and text != "\n":
                        parts.append(text)
            return " ".join(parts).strip() or None
        except json.JSONDecodeError:
            return None
    return _parse_vtt(body) or None


def _is_short(info: dict[str, Any]) -> bool:
    page = info.get("webpage_url") or info.get("original_url") or ""
    if "/shorts/" in page:
        return True
    duration = info.get("duration")
    return (
        isinstance(duration, (int, float))
        and duration <= 60
        and (info.get("height") or 0) >= (info.get("width") or 0)
    )


def _build_suggested_comment(
    info: dict[str, Any], channel: str, upload_date: str | None
) -> str | None:
    parts: list[str] = []
    if channel:
        line = f"YouTube source: {channel}"
        if upload_date:
            line += f" (uploaded {upload_date})"
        parts.append(line)
    desc = (info.get("description") or "").strip()
    if desc:
        snippet = desc[:1500]
        if len(desc) > 1500:
            snippet += "…"
        parts.append(snippet)
    return "\n\n".join(parts) if parts else None


def _thumbnail_url(info: dict[str, Any], youtube_id: str | None = None) -> str | None:
    thumbs = info.get("thumbnails") or []
    if thumbs:
        for pref in ("maxresdefault", "hqdefault", "mqdefault", "sddefault", "default"):
            for entry in reversed(thumbs):
                url = entry.get("url")
                if url and pref in url:
                    return url
        last = thumbs[-1].get("url")
        if last:
            return last
    thumb = info.get("thumbnail")
    if isinstance(thumb, str) and thumb:
        return thumb
    if youtube_id:
        from app.utils import youtube_thumbnail_url

        return youtube_thumbnail_url(youtube_id)
    return None


def fetch_youtube_thumbnail(url_or_id: str) -> str:
    """Best-effort thumbnail URL for a YouTube video."""
    youtube_id = extract_youtube_id(url_or_id)
    try:
        info = _run_ytdlp_json(youtube_watch_url(youtube_id))
        url = _thumbnail_url(info, youtube_id)
        if url:
            return url
    except Exception:
        logger.debug("Thumbnail fetch via yt-dlp failed for %s", youtube_id, exc_info=True)
    from app.utils import youtube_thumbnail_url

    return youtube_thumbnail_url(youtube_id)


def fetch_youtube_metadata(url_or_id: str) -> dict[str, Any]:
    """Return submission-friendly metadata for a YouTube URL or video ID."""
    youtube_id = extract_youtube_id(url_or_id)
    url = youtube_watch_url(youtube_id)
    info = _run_ytdlp_json(url)

    width = info.get("width")
    height = info.get("height")
    duration_sec = info.get("duration")
    description = (info.get("description") or "").strip()
    title = (info.get("title") or "").strip()
    channel = (info.get("channel") or info.get("uploader") or "").strip()
    tags = [str(t).strip() for t in (info.get("tags") or []) if str(t).strip()]

    transcript = _fetch_subtitle_text(info)
    if not transcript and description and len(description) <= 8000:
        transcript = description

    upload_date = _format_upload_date(info.get("upload_date"))
    resolution = f"{width}x{height}" if width and height else None
    is_short = _is_short(info)
    thumbnail_url = _thumbnail_url(info, youtube_id)

    metadata: dict[str, Any] = {
        "youtube_title": title,
        "youtube_description": description[:8000] if description else None,
        "youtube_channel_id": info.get("channel_id"),
        "youtube_channel_url": info.get("channel_url") or info.get("uploader_url"),
        "youtube_view_count": info.get("view_count"),
        "youtube_like_count": info.get("like_count"),
        "youtube_comment_count": info.get("comment_count"),
        "youtube_categories": info.get("categories") or [],
        "youtube_thumbnail": thumbnail_url,
        "youtube_live_status": info.get("live_status"),
        "youtube_availability": info.get("availability"),
        "youtube_is_short": is_short,
        "youtube_was_live": info.get("was_live"),
        "youtube_age_limit": info.get("age_limit"),
        "youtube_fps": info.get("fps"),
        "youtube_vcodec": info.get("vcodec"),
        "youtube_acodec": info.get("acodec"),
        "youtube_format_note": info.get("format_note") or info.get("format"),
        "youtube_playlist": info.get("playlist"),
        "youtube_playlist_index": info.get("playlist_index"),
    }
    metadata = {k: v for k, v in metadata.items() if v not in (None, "", [], {})}

    return {
        "youtube_id": youtube_id,
        "youtube_url": url,
        "title": title or None,
        "channel_name": channel or None,
        "upload_date": upload_date,
        "duration_ms": int(duration_sec * 1000) if duration_sec else None,
        "aspect_ratio": _aspect_ratio(width, height),
        "resolution": resolution,
        "language": _pick_language(info),
        "tags": tags[:30],
        "transcript": transcript[:12000] if transcript else None,
        "is_short": is_short,
        "suggested_comment": _build_suggested_comment(info, channel, upload_date),
        "thumbnail_url": thumbnail_url,
        "metadata": metadata,
    }
