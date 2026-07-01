"""Extract useful video/audio metadata from downloaded media via ffprobe and ffmpeg."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from math import gcd
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ISO639_2_TO_1 = {
    "eng": "en",
    "deu": "de",
    "ger": "de",
    "fra": "fr",
    "fre": "fr",
    "spa": "es",
    "ita": "it",
    "jpn": "ja",
    "por": "pt",
    "nld": "nl",
    "dut": "nl",
    "rus": "ru",
    "kor": "ko",
    "zho": "zh",
    "chi": "zh",
}

_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")
_MEAN_VOLUME = re.compile(r"mean_volume:\s*([-0-9.]+)\s*dB")
_MAX_VOLUME = re.compile(r"max_volume:\s*([-0-9.]+)\s*dB")


def _parse_frame_rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denominator = float(den)
            if denominator == 0:
                return None
            return round(float(num) / denominator, 3)
        except ValueError:
            return None
    try:
        return round(float(value), 3)
    except ValueError:
        return None


def _aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _first_stream(streams: list[dict[str, Any]], codec_type: str) -> dict[str, Any] | None:
    for stream in streams:
        if stream.get("codec_type") == codec_type:
            return stream
    return None


def _run_ffprobe_json(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "ffprobe failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON") from exc


def _run_ffmpeg_audio_analysis(path: Path) -> dict[str, Any]:
    """Silence and loudness stats from ffmpeg filter output (stderr)."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(path),
        "-vn",
        "-af",
        "silencedetect=noise=-40dB:d=0.3,volumedetect",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    stderr = result.stderr or ""
    silence_starts = [float(v) for v in _SILENCE_START.findall(stderr)]
    silence_ends = [float(v) for v in _SILENCE_END.findall(stderr)]
    mean_match = _MEAN_VOLUME.search(stderr)
    max_match = _MAX_VOLUME.search(stderr)

    analysis: dict[str, Any] = {}
    if silence_starts:
        analysis["silence_starts_sec"] = silence_starts[:20]
    if silence_ends:
        analysis["silence_ends_sec"] = silence_ends[:20]
    if silence_starts and silence_starts[0] <= 0.5:
        analysis["leading_silence_sec"] = silence_starts[0]
    if mean_match:
        analysis["mean_volume_db"] = float(mean_match.group(1))
    if max_match:
        analysis["max_volume_db"] = float(max_match.group(1))
    return analysis


def parse_ffprobe_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize ffprobe JSON into submission-friendly fields."""
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = _first_stream(streams, "video")
    audio = _first_stream(streams, "audio")

    width = int(video["width"]) if video and video.get("width") else None
    height = int(video["height"]) if video and video.get("height") else None
    duration_sec = None
    if fmt.get("duration"):
        try:
            duration_sec = float(fmt["duration"])
        except (TypeError, ValueError):
            duration_sec = None
    elif video and video.get("duration"):
        try:
            duration_sec = float(video["duration"])
        except (TypeError, ValueError):
            duration_sec = None

    fps = None
    if video:
        fps = _parse_frame_rate(video.get("avg_frame_rate")) or _parse_frame_rate(
            video.get("r_frame_rate")
        )

    audio_language = None
    if audio:
        tags = audio.get("tags") or {}
        raw_lang = tags.get("language") or tags.get("LANGUAGE")
        if isinstance(raw_lang, str):
            code = raw_lang.strip().lower().split("-")[0]
            audio_language = _ISO639_2_TO_1.get(code, code if len(code) == 2 else code)

    file_size = fmt.get("size")
    try:
        file_size_bytes = int(file_size) if file_size is not None else None
    except (TypeError, ValueError):
        file_size_bytes = None

    bit_rate = fmt.get("bit_rate")
    try:
        total_bit_rate = int(bit_rate) if bit_rate is not None else None
    except (TypeError, ValueError):
        total_bit_rate = None

    chapters = data.get("chapters") or []
    chapter_titles = [
        (ch.get("tags") or {}).get("title")
        for ch in chapters
        if (ch.get("tags") or {}).get("title")
    ]

    probe: dict[str, Any] = {
        "duration_sec": duration_sec,
        "width": width,
        "height": height,
        "aspect_ratio": _aspect_ratio(width, height),
        "resolution": f"{width}x{height}" if width and height else None,
        "fps": fps,
        "has_video": video is not None,
        "has_audio": audio is not None,
        "format_name": fmt.get("format_name"),
        "format_long_name": fmt.get("format_long_name"),
        "file_size_bytes": file_size_bytes,
        "bit_rate": total_bit_rate,
        "video_codec": video.get("codec_name") if video else None,
        "video_bit_rate": int(video["bit_rate"]) if video and video.get("bit_rate") else None,
        "pix_fmt": video.get("pix_fmt") if video else None,
        "color_space": video.get("color_space") if video else None,
        "display_aspect_ratio": video.get("display_aspect_ratio") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_bit_rate": int(audio["bit_rate"]) if audio and audio.get("bit_rate") else None,
        "audio_channels": int(audio["channels"]) if audio and audio.get("channels") else None,
        "audio_sample_rate": int(audio["sample_rate"])
        if audio and audio.get("sample_rate")
        else None,
        "audio_channel_layout": audio.get("channel_layout") if audio else None,
        "audio_language": audio_language,
        "stream_count": len(streams),
        "chapter_count": len(chapters),
        "chapter_titles": chapter_titles[:10],
    }
    return {k: v for k, v in probe.items() if v not in (None, "", [], {})}


def probe_media_file(path: Path) -> dict[str, Any]:
    """Run ffprobe + ffmpeg analysis on a downloaded media file."""
    raw = _run_ffprobe_json(path)
    probe = parse_ffprobe_data(raw)
    try:
        probe["audio_analysis"] = _run_ffmpeg_audio_analysis(path)
    except Exception:
        logger.debug("ffmpeg audio analysis failed for %s", path, exc_info=True)
    return probe


def probe_video_fields(probe: dict[str, Any]) -> dict[str, Any]:
    """Map probe output to Video / edit after_state fields."""
    fields: dict[str, Any] = {}
    if probe.get("duration_sec"):
        fields["duration_ms"] = int(float(probe["duration_sec"]) * 1000)
    if probe.get("aspect_ratio"):
        fields["aspect_ratio"] = probe["aspect_ratio"]
    if probe.get("resolution"):
        fields["resolution"] = probe["resolution"]
    if probe.get("audio_language"):
        fields["language"] = probe["audio_language"]
    fields["metadata"] = {"media_probe": probe}
    return fields


def merge_probe_into_state(state: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    """Fill missing video fields from probe; never overwrite user-provided values."""
    merged = dict(state)
    derived = probe_video_fields(probe)

    for key in ("duration_ms", "aspect_ratio", "resolution", "language", "thumbnail_url"):
        if key in derived and not merged.get(key):
            merged[key] = derived[key]

    if not merged.get("thumbnail_url") and merged.get("youtube_id"):
        from app.utils import youtube_thumbnail_url

        merged["thumbnail_url"] = youtube_thumbnail_url(str(merged["youtube_id"]))

    probe_meta = derived.get("metadata", {}).get("media_probe", probe)
    existing_meta = dict(merged.get("metadata") or {})
    existing_probe = dict(existing_meta.get("media_probe") or {})
    existing_probe.update(probe_meta)
    existing_meta["media_probe"] = existing_probe
    merged["metadata"] = existing_meta
    return merged
