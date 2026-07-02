"""Tests for yt-dlp download format fallback logic."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import media_hash


def test_download_youtube_tries_fallback_formats(tmp_path):
    calls: list[str] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[cmd.index("-f") + 1])
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
    assert calls[-1] == "worst"
    assert len(calls) >= 2


def test_download_youtube_raises_after_all_formats_fail(tmp_path):
    with patch(
        "app.services.media_hash.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="Requested format is not available"),
    ), patch("app.services.media_hash._ytdlp_version", return_value="2024.04.08"):
        with pytest.raises(RuntimeError, match="Requested format is not available"):
            media_hash.download_youtube("5uaYHYs4ubw", tmp_path)
