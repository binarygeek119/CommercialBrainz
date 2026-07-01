"""Tests for YouTube metadata parsing helpers."""

from app.services.youtube_metadata import (
    _aspect_ratio,
    _build_suggested_comment,
    _format_upload_date,
    _is_short,
    _parse_vtt,
)


def test_format_upload_date():
    assert _format_upload_date("20240315") == "2024-03-15"
    assert _format_upload_date("bad") is None


def test_aspect_ratio():
    assert _aspect_ratio(1920, 1080) == "16:9"
    assert _aspect_ratio(None, 1080) is None


def test_is_short():
    assert _is_short({"webpage_url": "https://youtube.com/shorts/abc12345678"}) is True
    assert _is_short({"duration": 30, "width": 1080, "height": 1920}) is True
    assert _is_short({"duration": 120, "width": 1920, "height": 1080}) is False


def test_build_suggested_comment():
    text = _build_suggested_comment(
        {"description": "Classic ad from the 90s."},
        "Brand Channel",
        "2019-03-15",
    )
    assert "Brand Channel" in text
    assert "Classic ad" in text


def test_parse_vtt():
    vtt = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
Hello world

2
00:00:03.000 --> 00:00:05.000
Hello world
"""
    assert _parse_vtt(vtt) == "Hello world"
