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
from app.models import (
    Edit,
    EditStatus,
    EditType,
    FingerprintStatus,
    MediaFingerprint,
    Video,
    VideoHashStatus,
)
from app.services.media_probe import merge_probe_into_state, probe_media_file, probe_video_fields
from app.services.phash import compute_phash, phash_to_db

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
    fmt: str | None,
    max_filesize_mb: int | None,
    merge_output_format: str | None,
    extractor_args: str | None = None,
) -> subprocess.CompletedProcess[str]:
    from app.services.ytdlp_auth import ytdlp_common_args

    cmd = [
        "yt-dlp",
        *ytdlp_common_args(extractor_args=extractor_args),
        "--no-playlist",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "-o",
        output_template,
    ]
    if fmt is not None:
        cmd.extend(["-f", fmt])
    if max_filesize_mb is not None:
        cmd.extend(["--max-filesize", f"{max_filesize_mb}M"])
    if merge_output_format:
        cmd.extend(["--merge-output-format", merge_output_format])
    cmd.append(url)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _format_attempts() -> list[tuple[str | None, int | None, str | None]]:
    """Primary format ladder: prefer low-res adaptive, then progressive, then any."""
    return [
        (settings.ytdlp_format, settings.hash_max_file_mb, "mp4"),
        ("bestvideo[height<=480]+bestaudio/best[height<=480]", settings.hash_max_file_mb, "mp4"),
        # Progressive itags often survive when DASH/SABR clients return no adaptive URLs.
        ("18/22/best[height<=480]/best", settings.hash_max_file_mb, None),
        ("bv*+ba/b", None, "mp4"),
        ("bestvideo+bestaudio/best", None, "mp4"),
        ("best", None, None),
        ("b", None, None),
        ("worstvideo+worstaudio/worst", None, "mp4"),
        ("worst", None, None),
        # Last resort: let yt-dlp pick without an explicit -f.
        (None, None, None),
    ]


def _extractor_attempts() -> list[str | None]:
    """
    Player-client variants. None means "use settings.ytdlp_extractor_args".
    Empty string omits --extractor-args (yt-dlp defaults).
    """
    configured = (settings.ytdlp_extractor_args or "").strip()
    attempts: list[str | None] = [None]
    for candidate in (
        "youtube:player_client=android,web,mweb",
        "youtube:player_client=android",
        "youtube:player_client=tv_embedded,web",
        "youtube:player_client=mweb,web",
        "",
    ):
        if candidate == configured:
            continue
        if candidate not in attempts:
            attempts.append(candidate)
    return attempts


def _recovery_format_attempts() -> list[tuple[str | None, int | None, str | None]]:
    """Shorter ladder used when switching player clients after format-unavailable."""
    return [
        ("18/22/best", None, None),
        ("best", None, None),
        ("b", None, None),
        (None, None, None),
    ]


def download_youtube(youtube_id: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    output_template = str(dest_dir / "%(id)s.%(ext)s")

    # max_filesize can exclude every format on some videos; merge can fail on odd codecs.
    last_error = "yt-dlp download failed"
    seen: set[tuple[str | None, str | None]] = set()

    def _try_batch(
        format_batch: list[tuple[str | None, int | None, str | None]],
        extractor_args: str | None,
    ) -> Path | None:
        nonlocal last_error
        for fmt, max_mb, merge_fmt in format_batch:
            key = (fmt, extractor_args if extractor_args is not None else "__settings__")
            if key in seen:
                continue
            seen.add(key)
            _clear_dest_files(dest_dir)

            result = _run_ytdlp_download(
                url=url,
                output_template=output_template,
                fmt=fmt,
                max_filesize_mb=max_mb,
                merge_output_format=merge_fmt,
                extractor_args=extractor_args,
            )
            if result.returncode != 0:
                last_error = (result.stderr or result.stdout or last_error).strip()
                logger.warning(
                    "yt-dlp format %r (extractor=%r) failed for %s: %s",
                    fmt,
                    extractor_args,
                    youtube_id,
                    last_error.splitlines()[-1] if last_error else "",
                )
                continue

            files = [p for p in dest_dir.iterdir() if p.is_file()]
            if files:
                logger.info(
                    "yt-dlp downloaded %s using format %r (extractor=%r)",
                    youtube_id,
                    fmt,
                    extractor_args,
                )
                return max(files, key=lambda p: p.stat().st_size)
            last_error = "yt-dlp produced no output file"
        return None

    # Pass 1: full format ladder with configured extractor args.
    path = _try_batch(_format_attempts(), None)
    if path is not None:
        return path

    # Pass 2: if formats were unavailable, retry other player clients with a short ladder.
    lowered = last_error.lower()
    if "format is not available" in lowered or "only images are available" in lowered:
        for extractor_args in _extractor_attempts()[1:]:
            path = _try_batch(_recovery_format_attempts(), extractor_args)
            if path is not None:
                return path

    version = _ytdlp_version()
    from app.services.ytdlp_auth import ytdlp_error_message

    detail = ytdlp_error_message(last_error or "yt-dlp download failed")
    raise RuntimeError(f"{detail} (yt-dlp {version}; video {youtube_id})")


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


def _set_video_hash_error(video: Video, message: str, *, permanent: bool) -> None:
    extra = dict(video.extra_data or {})
    extra["hash_error"] = message[:500]
    video.extra_data = extra
    video.hash_status = VideoHashStatus.FAILED if permanent else VideoHashStatus.PENDING


def _clear_video_hash_error(video: Video) -> None:
    extra = dict(video.extra_data or {})
    if "hash_error" in extra:
        extra = dict(extra)
        extra.pop("hash_error", None)
        video.extra_data = extra


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
            fp.phash = phash_to_db(phash)
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
        error_text = str(exc)[:2000]
        async with async_session_factory() as db:
            fp = await db.get(MediaFingerprint, fingerprint_id)
            if fp:
                fp.retry_count += 1
                fp.error_message = error_text
                fp.completed_at = datetime.now(UTC)
                permanent = fp.retry_count >= settings.fingerprint_max_retries
                fp.status = FingerprintStatus.FAILED
                if fp.video_id:
                    video = await db.get(Video, fp.video_id)
                    if video:
                        _set_video_hash_error(video, error_text, permanent=permanent)
                await db.commit()
                if not permanent:
                    logger.info(
                        "Fingerprint job %s failed (attempt %d/%d); cron will retry",
                        fingerprint_id,
                        fp.retry_count,
                        settings.fingerprint_max_retries,
                    )
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
    _clear_video_hash_error(video)
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
