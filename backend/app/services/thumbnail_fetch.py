"""Fetch / verify YouTube thumbnails after submit; fallback to a streamed frame."""

from __future__ import annotations

import logging
import random
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Video
from app.services.thumbnail_storage import (
    hosted_thumbnail_exists,
    is_hosted_thumbnail,
    save_video_thumbnail,
)
from app.services.ytdlp_auth import ytdlp_common_args, ytdlp_error_message
from app.utils import youtube_thumbnail_url, youtube_watch_url

logger = logging.getLogger(__name__)
settings = get_settings()

THUMB_META_KEY = "thumbnail_fetch"
CDN_QUALITIES = ("maxresdefault", "sddefault", "hqdefault", "mqdefault", "default")
# YouTube gray "no thumbnail" placeholders are small / nearly solid.
_MIN_BYTES = 2048
_MIN_PIXELS = 10_000


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_thumbnail_fetch_meta(video: Video) -> dict[str, Any]:
    extra = dict(video.extra_data or {})
    meta = extra.get(THUMB_META_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def set_thumbnail_fetch_meta(video: Video, **updates: Any) -> None:
    extra = dict(video.extra_data or {})
    meta = dict(extra.get(THUMB_META_KEY) or {})
    meta.update(updates)
    extra[THUMB_META_KEY] = meta
    video.extra_data = extra


def mark_thumbnail_fetch_pending(video: Video) -> None:
    """Mark a newly created video so the worker verifies / materializes its thumb."""
    if is_hosted_thumbnail(video.thumbnail_url):
        set_thumbnail_fetch_meta(
            video,
            status="ok",
            attempts=0,
            source="hosted_upload",
            last_attempt_at=_now_iso(),
        )
        return
    if not video.youtube_id:
        return
    meta = get_thumbnail_fetch_meta(video)
    if meta.get("status") in {"ok", "exhausted_frame"}:
        return
    set_thumbnail_fetch_meta(
        video,
        status="pending",
        attempts=int(meta.get("attempts") or 0),
        last_attempt_at=meta.get("last_attempt_at"),
        last_error=meta.get("last_error"),
    )


def mark_thumbnail_force_refresh(video: Video) -> None:
    """
    Queue a forced re-fetch: stream a padded random frame (CDN only as fallback).

    Resets attempt counters so ensure_video_thumbnail(force=True) runs end-to-end.
    """
    if not video.youtube_id:
        raise ValueError("Video has no YouTube id")
    set_thumbnail_fetch_meta(
        video,
        status="pending",
        attempts=0,
        force=True,
        source=None,
        last_error=None,
        last_attempt_at=None,
        requested_at=_now_iso(),
    )


def _parse_meta_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def needs_force_thumbnail_regrab(
    video: Video,
    *,
    now: datetime | None = None,
) -> bool:
    """
    True when a public catalog video should get an automatic force re-grab.

    Targets empty thumbs, hosted URLs whose file is missing on disk, and
    recently failed fetches (subject to cooldown). Leaves healthy CDN-only
    and on-disk hosted thumbs alone.
    """
    if not video.youtube_id:
        return False

    meta = get_thumbnail_fetch_meta(video)
    status = str(meta.get("status") or "")
    # Already queued — process_thumbnail_retries / ensure_thumbnail handle these.
    if status in {"pending", "retry"}:
        return False

    url = (video.thumbnail_url or "").strip()
    if not url:
        return True

    if is_hosted_thumbnail(url):
        return not hosted_thumbnail_exists(url)

    if status == "failed":
        last = _parse_meta_time(meta.get("last_attempt_at")) or _parse_meta_time(
            meta.get("requested_at")
        )
        if last is None:
            return True
        cooldown = timedelta(hours=settings.thumbnail_missing_scan_cooldown_hours)
        stamp = now or datetime.now(UTC)
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return stamp - last >= cooldown

    return False


def padded_random_timestamp(
    duration_sec: float,
    *,
    pad_ratio: float | None = None,
    pad_seconds: float | None = None,
    rng: random.Random | None = None,
) -> float:
    """Pick a random time inside the video, padding start/end to avoid black frames."""
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    ratio = settings.thumbnail_frame_pad_ratio if pad_ratio is None else pad_ratio
    seconds = settings.thumbnail_frame_pad_seconds if pad_seconds is None else pad_seconds
    pad = max(float(seconds), float(ratio) * duration_sec)
    # Keep a usable window even on short clips.
    if duration_sec <= pad * 2 + 0.25:
        pad = max(0.0, duration_sec * 0.1)
    start = pad
    end = max(start, duration_sec - pad)
    picker = rng or random
    if end <= start:
        return max(0.0, duration_sec / 2.0)
    return float(picker.uniform(start, end))


def _is_usable_image(data: bytes) -> bool:
    if len(data) < _MIN_BYTES:
        return False
    try:
        img = Image.open(BytesIO(data))
        img.load()
        width, height = img.size
        if width * height < _MIN_PIXELS:
            return False
        # Reject near-solid placeholders (common YouTube gray default).
        sample = img.convert("RGB").resize((32, 32))
        colors = sample.getcolors(maxcolors=32 * 32) or []
        if len(colors) <= 4:
            return False
        return True
    except Exception:
        return False


def _candidate_urls(video: Video) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str | None) -> None:
        if not url or url in seen:
            return
        if url.startswith("/api/"):
            return
        seen.add(url)
        urls.append(url)

    add(video.thumbnail_url)
    extra = video.extra_data or {}
    add(extra.get("youtube_thumbnail") if isinstance(extra.get("youtube_thumbnail"), str) else None)
    if video.youtube_id:
        for quality in CDN_QUALITIES:
            add(youtube_thumbnail_url(video.youtube_id, quality))
    return urls


def download_cdn_thumbnail(video: Video) -> bytes | None:
    """HTTP-fetch a usable YouTube CDN (or remote) thumbnail."""
    headers = {"User-Agent": "CommercialBrainz/1.0"}
    with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
        for url in _candidate_urls(video):
            try:
                response = client.get(url)
                if response.status_code != 200:
                    continue
                data = response.content
                if _is_usable_image(data):
                    return data
            except Exception as exc:
                logger.debug("Thumbnail download failed for %s: %s", url, exc)
    return None


def _ytdlp_duration_sec(youtube_id: str) -> float:
    import json

    url = youtube_watch_url(youtube_id)
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        "--",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(ytdlp_error_message(result.stderr or result.stdout))
    info = json.loads(result.stdout)
    duration = info.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise RuntimeError("Could not determine video duration for frame extract")
    return float(duration)


def _ytdlp_stream_url(youtube_id: str) -> str:
    url = youtube_watch_url(youtube_id)
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--no-playlist",
        "-f",
        "best[height<=480]/worst",
        "-g",
        "--no-warnings",
        "--",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=90)
    if result.returncode != 0:
        raise RuntimeError(ytdlp_error_message(result.stderr or result.stdout))
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("yt-dlp returned no stream URL")
    # Prefer the last line (video when adaptive returns video+audio URLs).
    return lines[-1]


def _ffmpeg_frame_from_url(stream_url: str, timestamp: float) -> bytes:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        "-q:v",
        "3",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    if result.returncode != 0 or not result.stdout:
        err = (result.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(err.strip() or "ffmpeg frame extract failed")
    if not _is_usable_image(result.stdout):
        raise RuntimeError("Extracted frame was not a usable image")
    return result.stdout


def _ffmpeg_frame_from_file(video_path: Path, timestamp: float) -> bytes:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        "-q:v",
        "3",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, check=False, timeout=120)
    if result.returncode != 0 or not result.stdout:
        err = (result.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(err.strip() or "ffmpeg frame extract failed")
    if not _is_usable_image(result.stdout):
        raise RuntimeError("Extracted frame was not a usable image")
    return result.stdout


def _download_section_clip(youtube_id: str, timestamp: float, dest_dir: Path) -> Path:
    """Fallback: download a short section around the timestamp via yt-dlp."""
    start = max(0.0, timestamp - 1.0)
    end = timestamp + 2.0
    url = youtube_watch_url(youtube_id)
    out_tmpl = str(dest_dir / "clip.%(ext)s")
    cmd = [
        "yt-dlp",
        *ytdlp_common_args(),
        "--no-playlist",
        "-f",
        "best[height<=360]/worst",
        "--download-sections",
        f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts",
        "-o",
        out_tmpl,
        "--no-warnings",
        "--",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(ytdlp_error_message(result.stderr or result.stdout))
    files = [p for p in dest_dir.iterdir() if p.is_file()]
    if not files:
        raise RuntimeError("yt-dlp section download produced no file")
    return files[0]


def extract_random_frame_jpeg(youtube_id: str, duration_sec: float | None = None) -> bytes:
    """
    Grab a JPEG frame at a random padded timestamp via yt-dlp streaming (+ ffmpeg).

    Prefers streaming (`yt-dlp -g` + ffmpeg seek). Falls back to a short
    `--download-sections` clip if the direct stream URL cannot be decoded.
    """
    if duration_sec and duration_sec > 0:
        duration = float(duration_sec)
    else:
        duration = _ytdlp_duration_sec(youtube_id)
    timestamp = padded_random_timestamp(duration)
    logger.info(
        "Extracting thumbnail frame for %s at %.2fs (duration=%.2fs)",
        youtube_id,
        timestamp,
        duration,
    )
    try:
        stream_url = _ytdlp_stream_url(youtube_id)
        return _ffmpeg_frame_from_url(stream_url, timestamp)
    except Exception as stream_exc:
        logger.warning(
            "Stream frame extract failed for %s (%s); trying section download",
            youtube_id,
            stream_exc,
        )
        with tempfile.TemporaryDirectory(prefix="cb-thumb-") as tmp:
            clip = _download_section_clip(youtube_id, timestamp, Path(tmp))
            # Section file starts near `start`; seek a little into the clip.
            local_ts = min(1.0, max(0.1, timestamp - max(0.0, timestamp - 1.0)))
            return _ffmpeg_frame_from_file(clip, local_ts)


async def _host_extracted_frame(
    video: Video,
    *,
    attempts: int,
    last_error: str | None,
    status: str = "exhausted_frame",
) -> str:
    duration_sec = (video.duration_ms / 1000.0) if video.duration_ms else None
    frame = extract_random_frame_jpeg(video.youtube_id, duration_sec)
    hosted = save_video_thumbnail(video.sbid, frame, "image/jpeg")
    video.thumbnail_url = hosted
    set_thumbnail_fetch_meta(
        video,
        status=status,
        attempts=attempts,
        force=False,
        source="extracted_frame",
        last_error=last_error,
        last_attempt_at=_now_iso(),
    )
    logger.info("Hosted extracted-frame thumbnail for video %s", video.sbid)
    return status


async def ensure_video_thumbnail(
    db: AsyncSession,
    video_id: UUID,
    *,
    force: bool = False,
) -> str:
    """
    Verify / fetch a YouTube thumbnail for a video.

    Attempts 1–2: download CDN thumbnail.
    Attempt 3 (final): extract a random padded frame via yt-dlp streaming.

    When force=True (manual re-grab): always stream a padded random frame so the
    UI gets a new image (CDN often returns the same file and looks like a no-op).
    Falls back to hosting the CDN image only if frame extract fails.

    Returns status string: ok | retry | exhausted_frame | failed | skipped.
    """
    video = await db.get(Video, video_id)
    if not video:
        return "missing"

    meta = get_thumbnail_fetch_meta(video)
    force = bool(force or meta.get("force"))

    if is_hosted_thumbnail(video.thumbnail_url) and not force:
        set_thumbnail_fetch_meta(
            video,
            status="ok",
            source="hosted_upload",
            last_attempt_at=_now_iso(),
        )
        await db.flush()
        return "skipped"

    if not video.youtube_id:
        set_thumbnail_fetch_meta(
            video,
            status="failed",
            force=False,
            last_error="No youtube_id",
            last_attempt_at=_now_iso(),
        )
        await db.flush()
        return "failed"

    attempts = int(meta.get("attempts") or 0) + 1
    max_retries = settings.thumbnail_max_retries

    if force:
        # Manual re-grab must produce a visibly new thumbnail.
        try:
            status = await _host_extracted_frame(
                video,
                attempts=attempts,
                last_error=None,
                status="ok",
            )
            await db.flush()
            return status
        except Exception as frame_exc:
            error = str(frame_exc)[:500]
            logger.warning(
                "Force frame extract failed for %s (%s); falling back to CDN",
                video_id,
                error,
            )
            if is_hosted_thumbnail(video.thumbnail_url):
                video.thumbnail_url = youtube_thumbnail_url(video.youtube_id)
            data = download_cdn_thumbnail(video)
            if data:
                hosted = save_video_thumbnail(video.sbid, data, "image/jpeg")
                video.thumbnail_url = hosted
                set_thumbnail_fetch_meta(
                    video,
                    status="ok",
                    attempts=attempts,
                    force=False,
                    source="youtube_cdn_hosted",
                    last_error=error,
                    last_attempt_at=_now_iso(),
                )
                await db.flush()
                return "ok"
            set_thumbnail_fetch_meta(
                video,
                status="failed",
                attempts=attempts,
                force=False,
                last_error=f"frame extract: {error}"[:500],
                last_attempt_at=_now_iso(),
            )
            await db.flush()
            return "failed"

    try:
        data = download_cdn_thumbnail(video)
        if data:
            if not video.thumbnail_url:
                video.thumbnail_url = youtube_thumbnail_url(video.youtube_id)
            set_thumbnail_fetch_meta(
                video,
                status="ok",
                attempts=attempts,
                force=False,
                source="youtube_cdn",
                last_error=None,
                last_attempt_at=_now_iso(),
            )
            await db.flush()
            return "ok"

        if attempts >= max_retries:
            status = await _host_extracted_frame(video, attempts=attempts, last_error=None)
            await db.flush()
            return status

        set_thumbnail_fetch_meta(
            video,
            status="retry",
            attempts=attempts,
            last_error="YouTube thumbnail download failed or unusable",
            last_attempt_at=_now_iso(),
        )
        await db.flush()
        return "retry"

    except Exception as exc:
        error = str(exc)[:500]
        logger.exception("Thumbnail ensure failed for video %s", video_id)
        if attempts >= max_retries:
            try:
                status = await _host_extracted_frame(
                    video, attempts=attempts, last_error=error
                )
                await db.flush()
                return status
            except Exception as frame_exc:
                set_thumbnail_fetch_meta(
                    video,
                    status="failed",
                    attempts=attempts,
                    force=False,
                    last_error=f"{error}; frame extract: {frame_exc}"[:500],
                    last_attempt_at=_now_iso(),
                )
                await db.flush()
                return "failed"

        set_thumbnail_fetch_meta(
            video,
            status="retry",
            attempts=attempts,
            last_error=error,
            last_attempt_at=_now_iso(),
        )
        await db.flush()
        return "retry"
