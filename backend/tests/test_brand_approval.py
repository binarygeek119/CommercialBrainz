"""Tests for brand approval voting threshold."""

from app.models import EditType
from app.services import EditService


class _FakeEdit:
    edit_type = EditType.CREATE_ADVERTISER


class _FakeVideoEdit:
    edit_type = EditType.CREATE_VIDEO


def test_brand_vote_threshold():
    assert EditService._vote_threshold(_FakeEdit()) == 10


def test_video_vote_threshold():
    assert EditService._vote_threshold(_FakeVideoEdit()) == 3
