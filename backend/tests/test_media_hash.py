"""Tests for yt-dlp download format fallback logic."""

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
        # Succeed only after switching player client in recovery pass.
        if (
            "youtube:player_client=android" in extractor_args_seen
            and extractor_args_seen[-1] == "youtube:player_client=android"
            and "-f" in cmd
            and cmd[cmd.index("-f") + 1] == "18/22/best"
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
            "youtube:player_client=android,web,mweb",
        ),
        patch("app.services.media_hash.subprocess.run", side_effect=fake_run),
        patch("app.services.media_hash._ytdlp_version", return_value="2026.07.04"),
        patch(
            "app.services.ytdlp_auth.ytdlp_common_args",
            side_effect=lambda extractor_args=None: (
                ["--extractor-args", extractor_args]
                if extractor_args is not None and extractor_args != ""
                else (
                    ["--extractor-args", "youtube:player_client=android,web,mweb"]
                    if extractor_args is None
                    else []
                )
            ),
        ),
    ):
        path = media_hash.download_youtube("5uaYHYs4ubw", tmp_path)

    assert path.name == "5uaYHYs4ubw.mp4"
    assert "youtube:player_client=android" in extractor_args_seen


def test_download_youtube_raises_after_all_formats_fail(tmp_path):
    with patch(
        "app.services.media_hash.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="Requested format is not available"),
    ), patch("app.services.media_hash._ytdlp_version", return_value="2024.04.08"):
        with pytest.raises(RuntimeError, match="Requested format is not available"):
            media_hash.download_youtube("5uaYHYs4ubw", tmp_path)
