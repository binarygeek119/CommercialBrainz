"""Download YouTube media and compute phash, file SHA256, and Chromaprint fingerprint."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models import Edit, EditStatus, EditType, FingerprintStatus, MediaFingerprint, Video, VideoHashStatus
from app.services.media_probe import merge_probe_into_state, probe_media_file, probe_video_fields
from app.services.phash import compute_phash

logger = logging.getLogger(__name__)
settings = get_settings()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fpcalc_fingerprint(path: Path) -> str:
    cmd = ["fpcalc", "-json", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "fpcalc failed")
    data = json.loads(result.stdout)
    fingerprint = data.get("fingerprint")
    if not fingerprint:
        raise RuntimeError("fpcalc returned no fingerprint")
    return str(fingerprint)


def _ytdlp_version() -> str:
    result = subprocess.run(
        ["yt-dlp", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or result.stderr or "unknown").strip()


def _clear_dest_files(dest_dir: Path) -> None:
    for path in dest_dir.iterdir():
        if path.is_file():
            path.unlink()


def _run_ytdlp_download(
    *,
    url: str,
    output_template: str,
    fmt: str,
    max_filesize_mb: int | None,
    merge_output_format: str | None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "-f",
        fmt,
        "-o",
        output_template,
        url,
    ]
    if max_filesize_mb is not None:
        cmd.extend(["--max-filesize", f"{max_filesize_mb}M"])
    if merge_output_format:
        cmd.extend(["--merge-output-format", merge_output_format])
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def download_youtube(youtube_id: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    output_template = str(dest_dir / "%(id)s.%(ext)s")

    # max_filesize can exclude every format on some videos; merge can fail on odd codecs.
    attempts: list[tuple[str, int | None, str | None]] = [
        (settings.ytdlp_format, settings.hash_max_file_mb, "mp4"),
        ("bestvideo[height<=480]+bestaudio/best[height<=480]", settings.hash_max_file_mb, "mp4"),
        ("bv*+ba/b", None, "mp4"),
        ("bestvideo+bestaudio/best", None, "mp4"),
        ("b", None, None),
        ("worstvideo+worstaudio/worst", None, "mp4"),
        ("worst", None, None),
    ]
    seen: set[str] = set()
    last_error = "yt-dlp download failed"

    for fmt, max_mb, merge_fmt in attempts:
        if fmt in seen:
            continue
        seen.add(fmt)
        _clear_dest_files(dest_dir)

        result = _run_ytdlp_download(
            url=url,
            output_template=output_template,
            fmt=fmt,
            max_filesize_mb=max_mb,
            merge_output_format=merge_fmt,
        )
        if result.returncode != 0:
            last_error = (result.stderr or result.stdout or last_error).strip()
            logger.warning(
                "yt-dlp format %r failed for %s: %s",
                fmt,
                youtube_id,
                last_error.splitlines()[-1] if last_error else "",
            )
            continue

        files = [p for p in dest_dir.iterdir() if p.is_file()]
        if files:
            logger.info("yt-dlp downloaded %s using format %r", youtube_id, fmt)
            return max(files, key=lambda p: p.stat().st_size)
        last_error = "yt-dlp produced no output file"

    version = _ytdlp_version()
    raise RuntimeError(
        f"{last_error.splitlines()[-1] if last_error else 'yt-dlp download failed'} "
        f"(yt-dlp {version}; video {youtube_id})"
    )


def compute_all_hashes(video_path: Path, probe: dict) -> tuple[int, str, str, float]:
    duration_sec = float(probe.get("duration_sec") or 0)
    if duration_sec <= 0:
        raise RuntimeError("Could not determine media duration from ffprobe")
    phash = compute_phash(video_path, duration_sec)
    file_hash = sha256_file(video_path)
    audio_fp = fpcalc_fingerprint(video_path)
    return phash, file_hash, audio_fp, duration_sec


async def _merge_probe_into_edit(db: AsyncSession, edit_id: UUID, probe: dict) -> None:
    edit = await db.get(Edit, edit_id)
    if not edit or edit.status != EditStatus.OPEN:
        return
    if edit.edit_type not in (EditType.CREATE_VIDEO, EditType.EDIT_VIDEO):
        return
    edit.after_state = merge_probe_into_state(edit.after_state or {}, probe)


async def run_fingerprint_job(fingerprint_id: UUID) -> None:
    temp_dir = Path(settings.hash_temp_dir) / str(fingerprint_id)
    async with async_session_factory() as db:
        fp = await db.get(MediaFingerprint, fingerprint_id)
        if not fp:
            logger.warning("Fingerprint job %s not found", fingerprint_id)
            return
        if fp.status == FingerprintStatus.COMPLETED:
            return

        fp.status = FingerprintStatus.PROCESSING
        fp.started_at = datetime.now(UTC)
        fp.error_message = None
        await db.commit()

    try:
        video_path = download_youtube(
            (await _get_youtube_id(fingerprint_id)),
            temp_dir,
        )
        probe = probe_media_file(video_path)
        phash, file_hash, audio_fp, duration = compute_all_hashes(video_path, probe)

        async with async_session_factory() as db:
            fp = await db.get(MediaFingerprint, fingerprint_id)
            if not fp:
                return
            fp.phash = phash
            fp.file_sha256 = file_hash
            fp.audio_fingerprint = audio_fp
            fp.duration_sec = duration
            fp.probe_data = probe
            fp.status = FingerprintStatus.COMPLETED
            fp.completed_at = datetime.now(UTC)
            fp.error_message = None

            if fp.edit_id:
                await _merge_probe_into_edit(db, fp.edit_id, probe)

            if fp.video_id:
                await _copy_to_video(db, fp.video_id, fp)

            await db.commit()
            logger.info("Completed fingerprint job %s for %s", fingerprint_id, fp.youtube_id)

    except Exception as exc:
        logger.exception("Fingerprint job %s failed", fingerprint_id)
        async with async_session_factory() as db:
            fp = await db.get(MediaFingerprint, fingerprint_id)
            if fp:
                fp.status = FingerprintStatus.FAILED
                fp.error_message = str(exc)[:2000]
                fp.completed_at = datetime.now(UTC)
                if fp.video_id:
                    video = await db.get(Video, fp.video_id)
                    if video:
                        video.hash_status = VideoHashStatus.FAILED
                await db.commit()
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def _get_youtube_id(fingerprint_id: UUID) -> str:
    async with async_session_factory() as db:
        fp = await db.get(MediaFingerprint, fingerprint_id)
        if not fp:
            raise RuntimeError("Fingerprint record missing")
        return fp.youtube_id


def _apply_probe_to_video(video: Video, probe: dict) -> None:
    derived = probe_video_fields(probe)
    if derived.get("duration_ms") and not video.duration_ms:
        video.duration_ms = derived["duration_ms"]
    if derived.get("aspect_ratio") and not video.aspect_ratio:
        video.aspect_ratio = derived["aspect_ratio"]
    if derived.get("resolution") and not video.resolution:
        video.resolution = derived["resolution"]
    if derived.get("language") and not video.language:
        video.language = derived["language"]

    extra = dict(video.extra_data or {})
    media_probe = dict(extra.get("media_probe") or {})
    media_probe.update(probe)
    extra["media_probe"] = media_probe
    video.extra_data = extra


async def _copy_to_video(db: AsyncSession, video_id: UUID, fp: MediaFingerprint) -> None:
    video = await db.get(Video, video_id)
    if not video:
        return
    video.phash = fp.phash
    video.file_sha256 = fp.file_sha256
    video.audio_fingerprint = fp.audio_fingerprint
    video.hash_status = VideoHashStatus.COMPLETED
    video.hashed_at = datetime.now(UTC)
    if fp.duration_sec and not video.duration_ms:
        video.duration_ms = int(fp.duration_sec * 1000)
    if fp.probe_data:
        _apply_probe_to_video(video, fp.probe_data)
    if not video.thumbnail_url and fp.youtube_id:
        from app.utils import youtube_thumbnail_url

        video.thumbnail_url = youtube_thumbnail_url(fp.youtube_id)


async def copy_preview_to_video(db: AsyncSession, edit_id: UUID, video_id: UUID) -> bool:
    """Copy completed preview fingerprint to video row. Returns True if copied."""
    result = await db.execute(
        select(MediaFingerprint).where(
            MediaFingerprint.edit_id == edit_id,
            MediaFingerprint.status == FingerprintStatus.COMPLETED,
        )
    )
    fp = result.scalar_one_or_none()
    if not fp:
        return False

    fp.video_id = video_id
    await _copy_to_video(db, video_id, fp)
    return True
