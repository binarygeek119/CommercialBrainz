"""Tests for media hash parsing and lookup helpers."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models import VideoHashStatus, VideoVisibility
from app.services.fingerprint_queries import (
    HASH_TYPES,
    normalize_file_sha256,
    parse_phash_hex,
    video_hashes_dict,
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


def test_video_hashes_dict_exposes_all_types():
    sbid = uuid4()
    commercial_id = uuid4()
    unsigned = 0xABCDEF0123456789
    video = SimpleNamespace(
        sbid=sbid,
        youtube_id="dQw4w9WgXcQ",
        commercial_id=commercial_id,
        phash=phash_to_db(unsigned),
        file_sha256="b" * 64,
        audio_fingerprint="AQAAA...",
        hash_status=VideoHashStatus.COMPLETED,
        hashed_at=None,
        visibility=VideoVisibility.PUBLIC,
    )
    payload = video_hashes_dict(video)
    assert payload["sbid"] == sbid
    assert payload["phash"] == f"{unsigned:016x}"
    assert payload["file_sha256"] == "b" * 64
    assert payload["audio_fingerprint"] == "AQAAA..."
    assert payload["hash_status"] == "completed"
