"""Tests for yt-dlp cookie auth helpers and managed cookies storage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.ytdlp_auth import (
    ytdlp_auth_args,
    ytdlp_common_args,
    ytdlp_error_message,
    ytdlp_js_runtime_args,
)
from app.services.ytdlp_cookies import (
    clear_cookies,
    cookies_status,
    save_cookies_text,
    validate_cookies_text,
)


def _settings(
    *,
    cookies_file: str = "",
    managed: str = "",
    browser: str = "",
    extractor_args: str = "youtube:player_client=android,web,mweb",
):
    class S:
        ytdlp_cookies_file = cookies_file
        ytdlp_cookies_managed_path = managed
        ytdlp_cookies_from_browser = browser
        ytdlp_extractor_args = extractor_args

    return S()


def test_ytdlp_auth_args_prefer_cookies_file(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n")
    managed = tmp_path / "managed.txt"
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=_settings(
            cookies_file=str(cookies), managed=str(managed), browser="chrome"
        )),
        patch("app.services.ytdlp_auth.get_settings", return_value=_settings(
            cookies_file=str(cookies), managed=str(managed), browser="chrome"
        )),
    ):
        assert ytdlp_auth_args() == ["--cookies", str(cookies)]


def test_ytdlp_auth_args_uses_managed_when_no_override(tmp_path: Path):
    managed = tmp_path / "cookies.txt"
    managed.write_text("# Netscape HTTP Cookie File\nyoutube.com\tTRUE\t/\tFALSE\t0\tA\tb\n")
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=_settings(
            cookies_file="", managed=str(managed)
        )),
        patch("app.services.ytdlp_auth.get_settings", return_value=_settings(
            cookies_file="", managed=str(managed)
        )),
    ):
        assert ytdlp_auth_args() == ["--cookies", str(managed)]


def test_ytdlp_auth_args_browser_fallback(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=_settings(
            cookies_file="", managed=str(missing), browser="chrome:Profile 1"
        )),
        patch("app.services.ytdlp_auth.get_settings", return_value=_settings(
            cookies_file="", managed=str(missing), browser="chrome:Profile 1"
        )),
    ):
        assert ytdlp_auth_args() == ["--cookies-from-browser", "chrome:Profile 1"]


def test_ytdlp_auth_args_empty_when_unset(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=_settings(
            cookies_file="", managed=str(missing), browser=""
        )),
        patch("app.services.ytdlp_auth.get_settings", return_value=_settings(
            cookies_file="", managed=str(missing), browser=""
        )),
    ):
        assert ytdlp_auth_args() == []


def test_ytdlp_error_message_adds_cookie_hint():
    msg = ytdlp_error_message(
        "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies"
    )
    assert "Admin → YouTube cookies" in msg
    assert "Sign in to confirm" in msg


def test_ytdlp_error_message_adds_format_hint():
    msg = ytdlp_error_message(
        "ERROR: [youtube] eEb0cYq6dvI: Requested format is not available. Use --list-formats"
    )
    assert "JS runtime" in msg or "Node.js" in msg
    assert "Admin → YouTube cookies" in msg


def test_ytdlp_js_runtime_args_prefers_node():
    with patch("app.services.ytdlp_auth.shutil.which", side_effect=lambda n: "/usr/bin/node" if n == "node" else None):
        assert ytdlp_js_runtime_args() == ["--js-runtimes", "node"]


def test_ytdlp_common_args_includes_extractor_and_js(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n", encoding="utf-8")
    settings = _settings(cookies_file=str(cookies), managed=str(tmp_path / "other.txt"))
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.shutil.which", side_effect=lambda n: "/bin/node" if n == "node" else None),
    ):
        args = ytdlp_common_args()
    assert args[:3] == ["--cookies", str(cookies), "--js-runtimes"]
    assert "node" in args
    assert "--extractor-args" in args
    assert "youtube:player_client=android,web,mweb" in args


def test_save_and_clear_cookies(tmp_path: Path):
    managed = tmp_path / "cookies.txt"
    with patch("app.services.ytdlp_cookies.get_settings", return_value=_settings(
        managed=str(managed)
    )):
        status = save_cookies_text(
            "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tvalue\n"
        )
        assert status["present"] is True
        assert managed.is_file()
        assert "SID" in managed.read_text(encoding="utf-8")
        assert cookies_status()["size_bytes"] > 0

        cleared = clear_cookies()
        assert cleared["present"] is False
        assert not managed.exists()


def test_validate_cookies_rejects_garbage():
    with pytest.raises(ValueError, match="Does not look like"):
        validate_cookies_text("hello world")


def test_metadata_cmd_includes_cookies(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n", encoding="utf-8")
    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)

        class Result:
            returncode = 1
            stderr = "boom"
            stdout = ""

        return Result()

    settings = _settings(cookies_file=str(cookies), managed=str(tmp_path / "other.txt"))
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.get_settings", return_value=settings),
        patch("app.services.youtube_metadata.subprocess.run", side_effect=fake_run),
    ):
        from app.services.youtube_metadata import _run_ytdlp_json

        with pytest.raises(RuntimeError, match="boom"):
            _run_ytdlp_json("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert captured
    assert captured[0][0] == "yt-dlp"
    assert "--cookies" in captured[0]
    assert str(cookies) in captured[0]
