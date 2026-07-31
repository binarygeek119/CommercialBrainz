"""Tests for cookie encryption and encrypted at-rest storage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import cookie_crypto as crypto
from app.services import ytdlp_cookies as yc

# Meets MIN_SEED_LENGTH (64).
_TEST_SEED = "test-cookie-seed-value-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def _settings(*, seed: str = _TEST_SEED, managed: str = ""):
    class S:
        cookie_encryption_seed = seed
        ytdlp_cookies_managed_path = managed
        ytdlp_cookies_file = ""
        ytdlp_cookies_from_browser = ""

    return S()


def test_encrypt_decrypt_roundtrip():
    with patch.object(crypto, "get_settings", return_value=_settings()):
        crypto._fernet_from_seed.cache_clear()
        plain = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tsecret\n"
        blob = crypto.encrypt_cookies(plain)
        assert blob.startswith(crypto.ENC_PREFIX)
        assert "secret" not in blob
        assert crypto.decrypt_cookies(blob) == plain


def test_encrypt_requires_seed():
    with patch.object(crypto, "get_settings", return_value=_settings(seed="")):
        crypto._fernet_from_seed.cache_clear()
        with pytest.raises(crypto.CookieEncryptionError, match="COOKIE_ENCRYPTION_SEED"):
            crypto.encrypt_cookies(".youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n")


def test_encrypt_rejects_short_seed():
    with patch.object(
        crypto,
        "get_settings",
        return_value=_settings(seed="only-32-chars-not-enough!!!!!!!!!!!"),
    ):
        crypto._fernet_from_seed.cache_clear()
        with pytest.raises(crypto.CookieEncryptionError, match="at least 64"):
            crypto.encrypt_cookies(".youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n")


def test_wrong_seed_fails_decrypt():
    with patch.object(crypto, "get_settings", return_value=_settings(seed=_TEST_SEED)):
        crypto._fernet_from_seed.cache_clear()
        blob = crypto.encrypt_cookies(".youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n")
    other = "different-seed-value-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    with patch.object(crypto, "get_settings", return_value=_settings(seed=other)):
        crypto._fernet_from_seed.cache_clear()
        with pytest.raises(crypto.CookieEncryptionError, match="decrypt"):
            crypto.decrypt_cookies(blob)


def test_legacy_plaintext_passthrough():
    with patch.object(crypto, "get_settings", return_value=_settings()):
        crypto._fernet_from_seed.cache_clear()
        legacy = ".youtube.com\tTRUE\t/\tFALSE\t0\tSID\told\n"
        assert crypto.decrypt_cookies(legacy) == legacy


def test_cookie_encryption_configured_requires_min_length():
    with patch.object(crypto, "get_settings", return_value=_settings(seed="short")):
        assert crypto.cookie_encryption_configured() is False
    with patch.object(crypto, "get_settings", return_value=_settings(seed=_TEST_SEED)):
        assert crypto.cookie_encryption_configured() is True


def test_save_cookies_writes_encrypted_and_materialized(tmp_path: Path):
    managed = tmp_path / "cookies.txt"
    settings = _settings(managed=str(managed))
    with (
        patch.object(yc, "get_settings", return_value=settings),
        patch.object(crypto, "get_settings", return_value=settings),
    ):
        crypto._fernet_from_seed.cache_clear()
        status = yc.save_cookies_text(
            "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tvalue\n"
        )
        enc = Path(str(managed) + ".enc")
        assert enc.is_file()
        assert managed.is_file()
        assert "SID\tvalue" in managed.read_text(encoding="utf-8")
        assert "SID\tvalue" not in enc.read_text(encoding="utf-8")
        assert status["encrypted_at_rest"] is True
        assert status["encryption_configured"] is True

        # Wipe plaintext and rematerialize from ciphertext.
        managed.unlink()
        path = yc.materialize_managed_cookies()
        assert path == managed
        assert "SID\tvalue" in managed.read_text(encoding="utf-8")
