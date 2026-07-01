"""Tests for custom thumbnail uploads."""

import pytest

from app.services.thumbnail_storage import validate_thumbnail_bytes

# Minimal valid 1x1 PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_validate_thumbnail_png():
    assert validate_thumbnail_bytes(TINY_PNG) == "image/png"


def test_validate_thumbnail_rejects_text():
    with pytest.raises(ValueError, match="JPEG, PNG, or WebP"):
        validate_thumbnail_bytes(b"not an image")
