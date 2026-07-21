"""Tests for transparent PNG, WebP, and SVG brand logo uploads."""

from io import BytesIO

import pytest
from PIL import Image

from app.services.logo_storage import (
    process_logo,
    process_logo_png,
    process_logo_svg,
    process_logo_webp,
)


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


def _transparent_webp() -> bytes:
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 128))
    buf = BytesIO()
    img.save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def _opaque_webp() -> bytes:
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def _simple_svg() -> bytes:
    return (
        b'<?xml version="1.0"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        b'<circle cx="32" cy="32" r="24" fill="red"/></svg>'
    )


def _malicious_svg() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        b'<script>alert("x")</script>'
        b'<foreignObject><body xmlns="http://www.w3.org/1999/xhtml">x</body></foreignObject>'
        b'<a href="javascript:alert(1)">link</a>'
        b"</svg>"
    )


def test_process_logo_accepts_transparent_png():
    out = process_logo_png(_transparent_png())
    assert out.startswith(b"\x89PNG")


def test_process_logo_rejects_opaque_png():
    with pytest.raises(ValueError, match="transparency"):
        process_logo_png(_opaque_png())


def test_process_logo_accepts_svg():
    out, ext = process_logo(_simple_svg())
    assert ext == ".svg"
    assert b"<svg" in out.lower()
    assert b"<script" not in out.lower()


def test_process_logo_svg_strips_unsafe_markup():
    out = process_logo_svg(_malicious_svg())
    text = out.decode("utf-8").lower()
    assert "<svg" in text
    assert "<script" not in text
    assert "onload=" not in text
    assert "javascript:" not in text
    assert "<foreignobject" not in text


def test_process_logo_detects_png():
    _, ext = process_logo(_transparent_png())
    assert ext == ".png"


def test_process_logo_accepts_transparent_webp():
    out = process_logo_webp(_transparent_webp())
    assert out[:4] == b"RIFF"
    assert out[8:12] == b"WEBP"


def test_process_logo_rejects_opaque_webp():
    with pytest.raises(ValueError, match="transparency"):
        process_logo_webp(_opaque_webp())


def test_process_logo_detects_webp():
    _, ext = process_logo(_transparent_webp())
    assert ext == ".webp"
