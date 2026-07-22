"""Unit tests for commercials list thumbnail selection."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.models import VideoVisibility
from app.services.video_response import commercial_list_thumbnail_url
from app.utils import youtube_thumbnail_url


def _video(**kwargs):
    defaults = {
        "sbid": uuid4(),
        "visibility": VideoVisibility.PUBLIC,
        "thumbnail_url": None,
        "youtube_id": None,
        "popularity_score": 0,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "youtube_url": None,
        "channel_name": None,
        "upload_date": None,
        "duration_ms": None,
        "aspect_ratio": None,
        "resolution": None,
        "language": None,
        "region": None,
        "sub_region": None,
        "market": None,
        "first_aired_date": None,
        "last_aired_date": None,
        "network": None,
        "transcript": None,
        "slogan": None,
        "cta_text": None,
        "extra_data": {},
        "phash": None,
        "file_sha256": None,
        "audio_fingerprint": None,
        "hash_status": None,
        "hashed_at": None,
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "commercial_id": uuid4(),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_prefers_main_video_thumbnail():
    main_id = uuid4()
    other_id = uuid4()
    commercial = SimpleNamespace(
        main_video_id=main_id,
        videos=[
            _video(sbid=other_id, thumbnail_url="https://example.com/other.jpg", popularity_score=99),
            _video(sbid=main_id, thumbnail_url="https://example.com/main.jpg", popularity_score=0),
        ],
    )
    assert commercial_list_thumbnail_url(commercial) == "https://example.com/main.jpg"


def test_falls_back_to_youtube_cdn():
    youtube_id = "dQw4w9WgXcQ"
    commercial = SimpleNamespace(
        main_video_id=None,
        videos=[_video(youtube_id=youtube_id)],
    )
    assert commercial_list_thumbnail_url(commercial) == youtube_thumbnail_url(youtube_id)


def test_skips_non_public_videos():
    commercial = SimpleNamespace(
        main_video_id=None,
        videos=[
            _video(
                visibility=VideoVisibility.DMCA_HIDDEN,
                thumbnail_url="https://example.com/hidden.jpg",
                youtube_id="abc",
            ),
        ],
    )
    assert commercial_list_thumbnail_url(commercial) is None
