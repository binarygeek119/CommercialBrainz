import re
from urllib.parse import parse_qs, urlparse

from slugify import slugify


def extract_youtube_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or raw ID."""
    value = url_or_id.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value

    parsed = urlparse(value)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("/")[0]
    if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]
        match = re.match(r"^/(embed|v|shorts)/([\w-]{11})", parsed.path)
        if match:
            return match.group(2)
    raise ValueError("Invalid YouTube URL or ID")


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def make_unique_slug(base: str, existing: set[str]) -> str:
    slug = slugify(base) or "item"
    if slug not in existing:
        return slug
    i = 2
    while f"{slug}-{i}" in existing:
        i += 1
    return f"{slug}-{i}"
