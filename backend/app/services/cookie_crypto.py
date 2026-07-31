"""Encrypt/decrypt YouTube cookies.txt at rest using a site operator seed.

Set COOKIE_ENCRYPTION_SEED in the environment (a long random passphrase you choose,
at least 64 characters). Donated cookies in the database and the admin-managed cookie
file are stored encrypted. A short-lived plaintext file is materialized only for yt-dlp
to read.
"""

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

logger = logging.getLogger(__name__)

# Versioned ciphertext prefix so we can detect encrypted blobs vs legacy plaintext.
ENC_PREFIX = "cbenc1:"
# Operator-chosen seed must be long enough to resist guessing / brute force.
MIN_SEED_LENGTH = 64
# Fixed salt mixed with a digest of the seed so different seeds still get distinct keys
# without requiring a stored salt column. Not a secret by itself.
_KDF_SALT_BASE = b"commercialbrainz-cookie-v1"
_KDF_ITERATIONS = 390_000


class CookieEncryptionError(ValueError):
    """Raised when the encryption seed is missing or ciphertext cannot be unlocked."""


def cookie_encryption_configured() -> bool:
    seed = (get_settings().cookie_encryption_seed or "").strip()
    return len(seed) >= MIN_SEED_LENGTH


def _require_seed() -> str:
    seed = (get_settings().cookie_encryption_seed or "").strip()
    if not seed:
        raise CookieEncryptionError(
            "COOKIE_ENCRYPTION_SEED is not set. Choose a long random passphrase "
            f"(at least {MIN_SEED_LENGTH} characters) and set it in the environment "
            "before saving or accepting YouTube cookies."
        )
    if len(seed) < MIN_SEED_LENGTH:
        raise CookieEncryptionError(
            f"COOKIE_ENCRYPTION_SEED must be at least {MIN_SEED_LENGTH} characters "
            f"(currently {len(seed)})"
        )
    return seed


@lru_cache(maxsize=8)
def _fernet_from_seed(seed: str) -> Fernet:
    # Salt includes a seed digest so two different seeds never share a KDF salt collision.
    salt = hashlib.sha256(_KDF_SALT_BASE + seed.encode("utf-8")).digest()[:16]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(seed.encode("utf-8")))
    return Fernet(key)


def is_encrypted_blob(text: str) -> bool:
    return (text or "").startswith(ENC_PREFIX)


def encrypt_cookies(plaintext: str) -> str:
    """Return versioned ciphertext for DB / disk storage."""
    cleaned = plaintext if plaintext.endswith("\n") else plaintext + "\n"
    token = _fernet_from_seed(_require_seed()).encrypt(cleaned.encode("utf-8"))
    return ENC_PREFIX + token.decode("ascii")


def decrypt_cookies(blob: str) -> str:
    """
    Decrypt a stored blob. Legacy plaintext (no prefix) is returned as-is so older
    rows/files keep working until re-saved under the seed.
    """
    raw = blob or ""
    if not is_encrypted_blob(raw):
        return raw
    token = raw[len(ENC_PREFIX) :].encode("ascii")
    try:
        plain = _fernet_from_seed(_require_seed()).decrypt(token)
    except InvalidToken as exc:
        raise CookieEncryptionError(
            "Could not decrypt cookies — COOKIE_ENCRYPTION_SEED may be wrong or the data is corrupt"
        ) from exc
    return plain.decode("utf-8")
