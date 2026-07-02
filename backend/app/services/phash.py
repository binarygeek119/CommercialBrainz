"""Stash-style video perceptual hash (5x5 sprite montage + pHash)."""

from __future__ import annotations

import logging
import subprocess
from io import BytesIO
from pathlib import Path

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)

SCREENSHOT_SIZE = 160
COLUMNS = 5
ROWS = 5
CHUNK_COUNT = COLUMNS * ROWS


def _run_ffmpeg_screenshot(video_path: Path, timestamp: float, slow_seek: bool) -> Image.Image:
    seek_before = ["-ss", str(timestamp)] if slow_seek else []
    seek_after = [] if slow_seek else ["-ss", str(timestamp)]
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        *seek_before,
        "-i",
        str(video_path),
        *seek_after,
        "-frames:v",
        "1",
        "-vf",
        f"scale={SCREENSHOT_SIZE}:{SCREENSHOT_SIZE}",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode() or "ffmpeg screenshot failed")
    img = Image.open(BytesIO(result.stdout))
    return img.convert("RGB")


def _combine_images(images: list[Image.Image]) -> Image.Image:
    width = images[0].width
    height = images[0].height
    canvas = Image.new("RGB", (width * COLUMNS, height * ROWS))
    for index, img in enumerate(images):
        x = width * (index % COLUMNS)
        y = height * (index // COLUMNS)
        canvas.paste(img, (x, y))
    return canvas


def generate_sprite(video_path: Path, duration_sec: float) -> Image.Image:
    """Build 5x5 contact sheet sampled between 5% and 95% of duration."""
    offset = 0.05 * duration_sec
    step_size = (0.9 * duration_sec) / CHUNK_COUNT
    images: list[Image.Image] = []
    slow_seek = False

    for i in range(CHUNK_COUNT):
        timestamp = offset + (i * step_size)
        try:
            img = _run_ffmpeg_screenshot(video_path, timestamp, slow_seek)
        except RuntimeError as first_err:
            if slow_seek:
                raise
            logger.warning(
                "Fast phash screenshot seek failed at %.3fs, retrying with accurate seek: %s",
                timestamp,
                first_err,
            )
            slow_seek = True
            img = _run_ffmpeg_screenshot(video_path, timestamp, slow_seek)
        images.append(img)

    if not images:
        raise RuntimeError(f"Failed to generate phash sprite for {video_path}")
    return _combine_images(images)


def compute_phash(video_path: Path, duration_sec: float) -> int:
    """Return 64-bit perceptual hash as unsigned integer."""
    sprite = generate_sprite(video_path, duration_sec)
    hash_obj = imagehash.phash(sprite)
    return phash_as_unsigned(int(str(hash_obj), 16))


def phash_as_unsigned(phash: int) -> int:
    """Normalize a stored or computed pHash to unsigned 64-bit."""
    return phash & 0xFFFFFFFFFFFFFFFF


def phash_to_db(phash: int) -> int:
    """Convert unsigned 64-bit pHash to signed BIGINT for PostgreSQL."""
    unsigned = phash_as_unsigned(phash)
    if unsigned >= 2**63:
        return unsigned - 2**64
    return unsigned


def hamming_distance(phash_a: int, phash_b: int) -> int:
    a = phash_as_unsigned(phash_a)
    b = phash_as_unsigned(phash_b)
    return (a ^ b).bit_count()
