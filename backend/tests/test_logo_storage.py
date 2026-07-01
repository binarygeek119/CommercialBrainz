"""Tests for transparent PNG brand logo uploads."""

from io import BytesIO

import pytest
from PIL import Image

from app.services.logo_storage import process_logo_png


def _transparent_png() -> bytes:
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 128))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _opaque_png() -> bytes:
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_process_logo_accepts_transparent_png():
    out = process_logo_png(_transparent_png())
    assert out.startswith(b"\x89PNG")


def test_process_logo_rejects_opaque_png():
    with pytest.raises(ValueError, match="transparency"):
        process_logo_png(_opaque_png())
