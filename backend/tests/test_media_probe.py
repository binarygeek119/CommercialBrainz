"""Tests for ffprobe parsing helpers."""

from app.services.media_probe import merge_probe_into_state, parse_ffprobe_data


def test_parse_ffprobe_data():
    raw = {
        "format": {
            "duration": "30.5",
            "format_name": "mp4",
            "size": "1048576",
            "bit_rate": "275000",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30/1",
                "pix_fmt": "yuv420p",
                "bit_rate": "250000",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "sample_rate": "48000",
                "tags": {"language": "eng"},
                "bit_rate": "128000",
            },
        ],
        "chapters": [],
    }
    probe = parse_ffprobe_data(raw)
    assert probe["duration_sec"] == 30.5
    assert probe["resolution"] == "1920x1080"
    assert probe["aspect_ratio"] == "16:9"
    assert probe["fps"] == 30.0
    assert probe["video_codec"] == "h264"
    assert probe["audio_codec"] == "aac"
    assert probe["audio_language"] == "en"


def test_merge_probe_into_state_preserves_user_values():
    state = {
        "language": "fr",
        "resolution": "1280x720",
        "metadata": {"source": "manual"},
    }
    probe = {
        "duration_sec": 15.0,
        "resolution": "1920x1080",
        "aspect_ratio": "16:9",
        "audio_language": "en",
        "video_codec": "h264",
    }
    merged = merge_probe_into_state(state, probe)
    assert merged["language"] == "fr"
    assert merged["resolution"] == "1280x720"
    assert merged["duration_ms"] == 15000
    assert merged["aspect_ratio"] == "16:9"
    assert merged["metadata"]["media_probe"]["video_codec"] == "h264"
    assert merged["metadata"]["source"] == "manual"
