"""Tests for yt-dlp download format fallback logic."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import media_hash


def test_download_youtube_tries_fallback_formats(tmp_path):
    calls: list[str | None] = []

    def fake_run(cmd, **kwargs):
        if "-f" in cmd:
            calls.append(cmd[cmd.index("-f") + 1])
        else:
            calls.append(None)
        if calls[-1] == "worst":
            (tmp_path / "5uaYHYs4ubw.mp4").write_bytes(b"ok")
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=1, stdout="", stderr="format not available")

    with patch.object(media_hash.settings, "ytdlp_format", "bad-format"), patch(
        "app.services.media_hash.subprocess.run", side_effect=fake_run
    ), patch("app.services.media_hash._ytdlp_version", return_value="2025.1.1"):
        path = media_hash.download_youtube("5uaYHYs4ubw", tmp_path)

    assert path.name == "5uaYHYs4ubw.mp4"
    assert calls[0] == "bad-format"
    assert "worst" in calls
    assert len(calls) >= 2


def test_download_youtube_retries_extractor_on_format_unavailable(tmp_path):
    extractor_args_seen: list[str | None] = []

    def fake_run(cmd, **kwargs):
        if "--extractor-args" in cmd:
            extractor_args_seen.append(cmd[cmd.index("--extractor-args") + 1])
        else:
            extractor_args_seen.append("")
        # Succeed after switching to a modern player client in recovery pass.
        if (
            extractor_args_seen[-1] == "youtube:player_client=android_vr,web_safari"
            and "-f" in cmd
            and cmd[cmd.index("-f") + 1] == "18/22/best[height<=480]/best"
        ):
            (tmp_path / "5uaYHYs4ubw.mp4").write_bytes(b"ok")
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(
            returncode=1,
            stdout="",
            stderr="ERROR: [youtube] 5uaYHYs4ubw: Requested format is not available",
        )

    with (
        patch.object(
            media_hash.settings,
            "ytdlp_extractor_args",
            "",
        ),
        patch("app.services.media_hash.subprocess.run", side_effect=fake_run),
        patch("app.services.media_hash._ytdlp_version", return_value="2026.07.04"),
        patch(
            "app.services.ytdlp_auth.ytdlp_common_args",
            side_effect=lambda extractor_args=None: (
                ["--extractor-args", extractor_args]
                if extractor_args is not None and extractor_args != ""
                else []
            ),
        ),
    ):
        path = media_hash.download_youtube("5uaYHYs4ubw", tmp_path)

    assert path.name == "5uaYHYs4ubw.mp4"
    assert "youtube:player_client=android_vr,web_safari" in extractor_args_seen


def test_extractor_attempts_prefer_modern_clients():
    with (
        patch.object(media_hash.settings, "ytdlp_extractor_args", ""),
        patch("app.services.media_hash.resolve_cookies_path", return_value=None),
    ):
        attempts = media_hash._extractor_attempts()
    # None uses settings (empty → yt-dlp defaults); "" is omitted as a duplicate.
    assert attempts[0] is None
    assert "youtube:player_client=android_vr,web_safari" in attempts
    assert "youtube:player_client=tv_downgraded,web_safari" in attempts
    assert "youtube:player_client=android,web,mweb" in attempts

    with (
        patch.object(media_hash.settings, "ytdlp_extractor_args", ""),
        patch(
            "app.services.media_hash.resolve_cookies_path",
            return_value=Path("/tmp/cookies.txt"),
        ),
    ):
        with_cookies = media_hash._extractor_attempts()
    assert "youtube:player_client=android,web,mweb" not in with_cookies

    with (
        patch.object(
            media_hash.settings,
            "ytdlp_extractor_args",
            "youtube:player_client=android,web,mweb",
        ),
        patch("app.services.media_hash.resolve_cookies_path", return_value=None),
    ):
        forced = media_hash._extractor_attempts()
    assert forced[0] is None
    assert "" in forced  # explicit yt-dlp defaults as recovery
    assert "youtube:player_client=android_vr,web_safari" in forced


def test_download_youtube_raises_after_all_formats_fail(tmp_path):
    with patch(
        "app.services.media_hash.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="Requested format is not available"),
    ), patch("app.services.media_hash._ytdlp_version", return_value="2024.04.08"):
        with pytest.raises(RuntimeError, match="Requested format is not available"):
            media_hash.download_youtube("5uaYHYs4ubw", tmp_path)


def test_run_ytdlp_download_returns_timeout_result():
    def fake_run(cmd, **kwargs):
        assert kwargs.get("timeout") == media_hash.settings.hash_download_timeout_sec
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    with patch("app.services.media_hash.subprocess.run", side_effect=fake_run):
        result = media_hash._run_ytdlp_download(
            url="https://www.youtube.com/watch?v=5uaYHYs4ubw",
            output_template="/tmp/%(id)s.%(ext)s",
            fmt="best",
            max_filesize_mb=None,
            merge_output_format=None,
        )
    assert result.returncode == 124
    assert "timed out" in (result.stderr or "").lower()


def test_fpcalc_fingerprint_times_out(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")

    with patch(
        "app.services.media_hash.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["fpcalc"], timeout=1),
    ):
        with pytest.raises(RuntimeError, match="fpcalc timed out"):
            media_hash.fpcalc_fingerprint(video)
