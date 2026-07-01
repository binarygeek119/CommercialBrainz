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
from app.models import FingerprintStatus, MediaFingerprint, Video, VideoHashStatus
from app.services.phash import compute_phash

logger = logging.getLogger(__name__)
settings = get_settings()


def probe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "ffprobe failed")
    return float(result.stdout.strip())


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


def download_youtube(youtube_id: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    output_template = str(dest_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        settings.ytdlp_format,
        "--max-filesize",
        f"{settings.hash_max_file_mb}M",
        "-o",
        output_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "yt-dlp download failed")

    files = [p for p in dest_dir.iterdir() if p.is_file()]
    if not files:
        raise RuntimeError("yt-dlp produced no output file")
    return max(files, key=lambda p: p.stat().st_size)


def compute_all_hashes(video_path: Path) -> tuple[int, str, str, float]:
    duration = probe_duration(video_path)
    phash = compute_phash(video_path, duration)
    file_hash = sha256_file(video_path)
    audio_fp = fpcalc_fingerprint(video_path)
    return phash, file_hash, audio_fp, duration


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
        phash, file_hash, audio_fp, duration = compute_all_hashes(video_path)

        async with async_session_factory() as db:
            fp = await db.get(MediaFingerprint, fingerprint_id)
            if not fp:
                return
            fp.phash = phash
            fp.file_sha256 = file_hash
            fp.audio_fingerprint = audio_fp
            fp.duration_sec = duration
            fp.status = FingerprintStatus.COMPLETED
            fp.completed_at = datetime.now(UTC)
            fp.error_message = None

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
