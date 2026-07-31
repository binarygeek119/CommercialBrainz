"""Tests for yt-dlp cookie auth helpers and managed cookies storage."""

from datetime import UTC, datetime
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
    extractor_args: str = "",
    cookie_seed: str = "test-cookie-seed-value-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
):
    class S:
        ytdlp_cookies_file = cookies_file
        ytdlp_cookies_managed_path = managed
        ytdlp_cookies_from_browser = browser
        ytdlp_extractor_args = extractor_args
        cookie_encryption_seed = cookie_seed

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
    def which(name: str):
        return "/usr/bin/node" if name == "node" else None

    with (
        patch("app.services.ytdlp_auth.shutil.which", side_effect=which),
        patch("app.services.ytdlp_auth.Path.is_file", return_value=True),
        patch("app.services.ytdlp_auth.os.access", return_value=True),
    ):
        assert ytdlp_js_runtime_args() == ["--js-runtimes", "node:/usr/bin/node"]


def test_ytdlp_common_args_includes_js_omits_empty_extractor(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n", encoding="utf-8")
    settings = _settings(cookies_file=str(cookies), managed=str(tmp_path / "other.txt"))

    def which(name: str):
        return "/bin/node" if name == "node" else None

    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.shutil.which", side_effect=which),
        patch("app.services.ytdlp_auth.Path.is_file", return_value=True),
        patch("app.services.ytdlp_auth.os.access", return_value=True),
    ):
        args = ytdlp_common_args()
    assert args[:2] == ["--cookies", str(cookies)]
    assert args[2:4] == ["--js-runtimes", "node:/bin/node"]
    assert "--extractor-args" not in args


def test_ytdlp_common_args_includes_explicit_extractor(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n", encoding="utf-8")
    settings = _settings(
        cookies_file=str(cookies),
        managed=str(tmp_path / "other.txt"),
        extractor_args="youtube:player_client=android_vr",
    )

    def which(name: str):
        return "/bin/node" if name == "node" else None

    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.get_settings", return_value=settings),
        patch("app.services.ytdlp_auth.shutil.which", side_effect=which),
        patch("app.services.ytdlp_auth.Path.is_file", return_value=True),
        patch("app.services.ytdlp_auth.os.access", return_value=True),
    ):
        args = ytdlp_common_args()
    assert "--extractor-args" in args
    assert "youtube:player_client=android_vr" in args


def test_save_and_clear_cookies(tmp_path: Path):
    managed = tmp_path / "cookies.txt"
    settings = _settings(managed=str(managed))
    with (
        patch("app.services.ytdlp_cookies.get_settings", return_value=settings),
        patch("app.services.cookie_crypto.get_settings", return_value=settings),
    ):
        from app.services.cookie_crypto import _fernet_from_seed

        _fernet_from_seed.cache_clear()
        far = int(datetime.now(UTC).timestamp()) + 86400 * 30
        status = save_cookies_text(
            "# Netscape HTTP Cookie File\n"
            f".youtube.com\tTRUE\t/\tFALSE\t{far}\tSID\tvalue\n"
            f".google.com\tTRUE\t/\tTRUE\t{far}\t__Secure-1PSID\tabc\n"
        )
        assert status["present"] is True
        assert managed.is_file()
        assert "SID" in managed.read_text(encoding="utf-8")
        assert Path(str(managed) + ".enc").is_file()
        assert cookies_status()["size_bytes"] > 0
        assert status["encrypted_at_rest"] is True
        assert status["auth_cookie_count"] >= 2
        assert status["expired"] is False
        assert status["expiry_known"] is True

        cleared = clear_cookies()
        assert cleared["present"] is False
        assert not managed.exists()
        assert not Path(str(managed) + ".enc").exists()


def test_analyze_cookies_detects_expired(tmp_path: Path):
    from app.services.ytdlp_cookies import analyze_cookies_file

    path = tmp_path / "cookies.txt"
    past = int(datetime.now(UTC).timestamp()) - 3600
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        f".youtube.com\tTRUE\t/\tFALSE\t{past}\tSID\told\n",
        encoding="utf-8",
    )
    analysis = analyze_cookies_file(path)
    assert analysis["expired"] is True
    assert analysis["needs_refresh"] is True
    assert analysis["auth_cookie_count"] == 1


def test_analyze_cookies_flags_missing_auth(tmp_path: Path):
    from app.services.ytdlp_cookies import analyze_cookies_file

    path = tmp_path / "cookies.txt"
    path.write_text(
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tFALSE\t0\tPREF\tf1=1\n",
        encoding="utf-8",
    )
    analysis = analyze_cookies_file(path)
    assert analysis["needs_refresh"] is True
    assert analysis["auth_cookie_count"] == 0


def test_probe_cookies_live_success(tmp_path: Path, monkeypatch):
    from app.services import ytdlp_cookies as yc

    managed = tmp_path / "cookies.txt"
    far = int(datetime.now(UTC).timestamp()) + 86400 * 10
    managed.write_text(
        "# Netscape HTTP Cookie File\n"
        f".youtube.com\tTRUE\t/\tFALSE\t{far}\tSID\tok\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(yc, "get_settings", lambda: _settings(managed=str(managed)))

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = '{"id": "jNQXAC9IVRw", "title": "Me at the zoo"}'
            stderr = ""

        return Result()

    monkeypatch.setattr(yc.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "app.services.ytdlp_auth.ytdlp_common_args",
        lambda **_kwargs: ["--cookies", str(managed)],
    )

    status = yc.probe_cookies_live()
    assert status["last_validation_ok"] is True
    assert status["needs_refresh"] is False


def test_probe_cookies_live_bot_check(tmp_path: Path, monkeypatch):
    from app.services import ytdlp_cookies as yc

    managed = tmp_path / "cookies.txt"
    far = int(datetime.now(UTC).timestamp()) + 86400 * 10
    managed.write_text(
        "# Netscape HTTP Cookie File\n"
        f".youtube.com\tTRUE\t/\tFALSE\t{far}\tSID\tok\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(yc, "get_settings", lambda: _settings(managed=str(managed)))

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "ERROR: Sign in to confirm you’re not a bot"

        return Result()

    monkeypatch.setattr(yc.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "app.services.ytdlp_auth.ytdlp_common_args",
        lambda **_kwargs: ["--cookies", str(managed)],
    )

    status = yc.probe_cookies_live()
    assert status["last_validation_ok"] is False
    assert status["needs_refresh"] is True


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
