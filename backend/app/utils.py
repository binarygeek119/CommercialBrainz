import re
from urllib.parse import parse_qs, urlparse

from slugify import slugify

_YOUTUBE_HOSTS = (
    "youtu.be",
    "www.youtu.be",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
)
# Common YouTube playlist id prefixes (uploads UU, likes LL, favorites FL, etc.).
_PLAYLIST_ID_RE = re.compile(r"^(?:PL|UU|LL|FL|OL|RD|SD)[\w-]{10,}$", re.IGNORECASE)


def extract_youtube_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or raw ID."""
    value = url_or_id.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value

    parsed = urlparse(value)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("/")[0]
    if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]
        match = re.match(r"^/(embed|v|shorts)/([\w-]{11})", parsed.path)
        if match:
            return match.group(2)
    raise ValueError("Invalid YouTube URL or ID")


def extract_youtube_playlist_id(url_or_id: str) -> str:
    """Extract YouTube playlist ID from playlist URL, watch+list URL, or raw ID."""
    value = (url_or_id or "").strip()
    if _PLAYLIST_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value)
    if parsed.hostname in _YOUTUBE_HOSTS:
        qs = parse_qs(parsed.query)
        list_ids = qs.get("list") or []
        if list_ids and _PLAYLIST_ID_RE.fullmatch(list_ids[0]):
            return list_ids[0]
    raise ValueError("Invalid YouTube playlist URL or ID")


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def youtube_playlist_url(playlist_id: str) -> str:
    return f"https://www.youtube.com/playlist?list={playlist_id}"


def youtube_thumbnail_url(video_id: str, quality: str = "hqdefault") -> str:
    """Direct YouTube CDN thumbnail URL (fallback when yt-dlp has no thumbnail field)."""
    return f"https://i.ytimg.com/vi/{video_id}/{quality}.jpg"


def make_unique_slug(base: str, existing: set[str]) -> str:
    slug = slugify(base) or "item"
    if slug not in existing:
        return slug
    i = 2
    while f"{slug}-{i}" in existing:
        i += 1
    return f"{slug}-{i}"
