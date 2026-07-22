"""Tests for power-user eligibility and bulk-import marker helpers."""

from types import SimpleNamespace

from app.auth.security import (
    user_bulk_submit_eligible,
    user_can_bulk_submit,
    user_can_see_bulk_import_marker,
)
from app.config import get_settings
from app.models import BULK_IMPORTED_TAG, UserRole
from app.services.bulk_import_marker import (
    ensure_bulk_imported_tag,
    filter_tags_for_viewer,
    normalize_user_tags,
)
from app.services.youtube_metadata import expand_youtube_playlist


def _user(**kwargs):
    defaults = {
        "role": UserRole.USER,
        "bulk_submit_enabled": False,
        "reputation_points": 0,
        "power_user_terms_version": None,
        "is_auto_editor": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_bulk_submit_eligible_by_reputation():
    settings = get_settings()
    below = settings.bulk_submit_min_reputation - 1
    assert not user_bulk_submit_eligible(_user(reputation_points=below))
    at_min = settings.bulk_submit_min_reputation
    assert user_bulk_submit_eligible(_user(reputation_points=at_min))


def test_bulk_submit_eligible_mod_admin():
    assert user_bulk_submit_eligible(_user(role=UserRole.MOD, reputation_points=0))
    assert user_bulk_submit_eligible(_user(role=UserRole.ADMIN, reputation_points=0))


def test_can_bulk_submit_requires_terms():
    user = _user(
        bulk_submit_enabled=True,
        reputation_points=600,
        power_user_terms_version=None,
    )
    assert not user_can_bulk_submit(user, active_terms_version=1)
    user.power_user_terms_version = 1
    assert user_can_bulk_submit(user, active_terms_version=1)


def test_normalize_strips_system_tag():
    assert BULK_IMPORTED_TAG not in normalize_user_tags(
        ["Foo", BULK_IMPORTED_TAG, "foo"]
    )


def test_ensure_bulk_imported_tag():
    tags = ensure_bulk_imported_tag(["Promo"])
    assert tags == ["promo", BULK_IMPORTED_TAG]


def test_filter_tags_for_viewer():
    tags = ["promo", BULK_IMPORTED_TAG]
    assert filter_tags_for_viewer(tags, None) == ["promo"]
    mod = _user(role=UserRole.MOD)
    assert BULK_IMPORTED_TAG in filter_tags_for_viewer(tags, mod)
    power = _user(bulk_submit_enabled=True, reputation_points=600)
    assert user_can_see_bulk_import_marker(power)
    assert BULK_IMPORTED_TAG in filter_tags_for_viewer(tags, power)


def test_expand_playlist_parses_entries(monkeypatch):
    def fake_flat(_url: str):
        return {
            "id": "PLtest",
            "title": "Test playlist",
            "entries": [
                {"id": "abcdefghijk", "title": "One"},
                {"id": "lmnopqrstuv", "title": "Two"},
            ],
        }

    monkeypatch.setattr(
        "app.services.youtube_metadata._run_ytdlp_playlist_flat",
        fake_flat,
    )
    result = expand_youtube_playlist(
        "https://youtube.com/playlist?list=PLtest",
        max_items=50,
    )
    assert result["playlist_id"] == "PLtest"
    assert len(result["entries"]) == 2
    assert result["entries"][0]["youtube_id"] == "abcdefghijk"
