"""Tests for yt-dlp cookie auth helpers."""

from pathlib import Path
from unittest.mock import patch

from app.services.ytdlp_auth import ytdlp_auth_args, ytdlp_error_message


def test_ytdlp_auth_args_prefer_cookies_file(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    with patch("app.services.ytdlp_auth.get_settings") as get_settings:
        get_settings.return_value.ytdlp_cookies_file = str(cookies)
        get_settings.return_value.ytdlp_cookies_from_browser = "chrome"
        assert ytdlp_auth_args() == ["--cookies", str(cookies)]


def test_ytdlp_auth_args_browser_fallback():
    with patch("app.services.ytdlp_auth.get_settings") as get_settings:
        get_settings.return_value.ytdlp_cookies_file = ""
        get_settings.return_value.ytdlp_cookies_from_browser = "chrome:Profile 1"
        assert ytdlp_auth_args() == ["--cookies-from-browser", "chrome:Profile 1"]


def test_ytdlp_auth_args_empty_when_unset():
    with patch("app.services.ytdlp_auth.get_settings") as get_settings:
        get_settings.return_value.ytdlp_cookies_file = ""
        get_settings.return_value.ytdlp_cookies_from_browser = ""
        assert ytdlp_auth_args() == []


def test_ytdlp_error_message_adds_cookie_hint():
    msg = ytdlp_error_message(
        "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies"
    )
    assert "YTDLP_COOKIES_FILE" in msg
    assert "Sign in to confirm" in msg


def test_metadata_cmd_includes_cookies(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n", encoding="utf-8")
    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        class Result:
            returncode = 1
            stderr = "boom"
            stdout = ""

        return Result()

    with patch("app.services.ytdlp_auth.get_settings") as get_settings, patch(
        "app.services.youtube_metadata.subprocess.run", side_effect=fake_run
    ):
        get_settings.return_value.ytdlp_cookies_file = str(cookies)
        get_settings.return_value.ytdlp_cookies_from_browser = ""
        from app.services.youtube_metadata import _run_ytdlp_json
        import pytest

        with pytest.raises(RuntimeError, match="boom"):
            _run_ytdlp_json("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert captured
    assert captured[0][:3] == ["yt-dlp", "--cookies", str(cookies)]
