"""Tests for media hash parsing and lookup helpers."""

import pytest

from app.services.fingerprint_queries import (
    HASH_TYPES,
    normalize_file_sha256,
    parse_phash_hex,
)
from app.services.phash import phash_as_unsigned, phash_to_db


def test_hash_types_include_all_media_hashes():
    assert HASH_TYPES == ("phash", "file_sha256", "audio_fingerprint")


def test_parse_phash_hex_round_trip():
    unsigned = 0xFCBAD00DBAD00D00
    hex_value = f"{unsigned:016x}"
    stored = parse_phash_hex(hex_value)
    assert phash_as_unsigned(stored) == unsigned
    assert stored == phash_to_db(unsigned)


def test_parse_phash_hex_accepts_0x_prefix():
    assert parse_phash_hex("0xabc") == parse_phash_hex("abc")


def test_parse_phash_hex_rejects_invalid():
    with pytest.raises(ValueError):
        parse_phash_hex("not-hex")
    with pytest.raises(ValueError):
        parse_phash_hex("1" * 17)


def test_normalize_file_sha256():
    digest = "a" * 64
    assert normalize_file_sha256(digest.upper()) == digest
    assert normalize_file_sha256("0x" + digest) == digest
    with pytest.raises(ValueError):
        normalize_file_sha256("abcd")
