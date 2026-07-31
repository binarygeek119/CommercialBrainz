"""Tests for power-user eligibility and bulk-import marker helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.auth.security import (
    user_bulk_submit_eligible,
    user_bulk_submit_granted,
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
from app.services.bulk_submit import classify_playlist_entries
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


def test_bulk_submit_granted_mod_admin_without_flag():
    assert user_bulk_submit_granted(_user(role=UserRole.MOD, reputation_points=0))
    assert user_bulk_submit_granted(_user(role=UserRole.ADMIN, reputation_points=0))
    assert not user_bulk_submit_granted(_user(reputation_points=600))
    assert user_bulk_submit_granted(
        _user(bulk_submit_enabled=True, reputation_points=600)
    )


def test_can_bulk_submit_requires_terms():
    user = _user(
        bulk_submit_enabled=True,
        reputation_points=600,
        power_user_terms_version=None,
    )
    assert not user_can_bulk_submit(user, active_terms_version=1)
    user.power_user_terms_version = 1
    assert user_can_bulk_submit(user, active_terms_version=1)


def test_admin_can_bulk_submit_after_terms():
    admin = _user(role=UserRole.ADMIN, reputation_points=0, power_user_terms_version=None)
    assert user_bulk_submit_granted(admin)
    assert not user_can_bulk_submit(admin, active_terms_version=1)
    admin.power_user_terms_version = 1
    assert user_can_bulk_submit(admin, active_terms_version=1)


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


@pytest.mark.asyncio
async def test_classify_playlist_entries_flags_duplicates(monkeypatch):
    catalog_sbid = uuid4()
    owner_id = uuid4()
    entries = [
        {"youtube_id": "aaaaaaaaaaa", "title": "New", "position": 0},
        {"youtube_id": "bbbbbbbbbbb", "title": "Catalog", "position": 1},
        {"youtube_id": "ccccccccccc", "title": "Queued", "position": 2},
        {"youtube_id": "aaaaaaaaaaa", "title": "New again", "position": 3},
    ]

    async def fake_catalog(_db, youtube_ids):
        return {"bbbbbbbbbbb": catalog_sbid}

    async def fake_queue(_db, _owner_id, youtube_ids):
        return {"ccccccccccc"}

    monkeypatch.setattr("app.services.bulk_submit._catalog_video_ids", fake_catalog)
    monkeypatch.setattr("app.services.bulk_submit._open_queue_youtube_ids", fake_queue)

    classified = await classify_playlist_entries(AsyncMock(), owner_id, entries)
    by_pos = {row["position"]: row for row in classified}
    assert by_pos[0]["status"] == "ok"
    assert by_pos[1]["reason"] == "catalog"
    assert by_pos[1]["existing_video_sbid"] == str(catalog_sbid)
    assert by_pos[2]["reason"] == "queue"
    assert by_pos[3]["reason"] == "playlist_duplicate"


@pytest.mark.asyncio
async def test_stage_next_bulk_items_respects_window(monkeypatch):
    from app.models import BulkSubmissionItemStatus
    from app.services import bulk_submit as bs

    monkeypatch.setattr(bs.settings, "bulk_submit_staging_window", 2)
    batch_id = uuid4()
    items = [
        SimpleNamespace(youtube_id="aaaaaaaaaaa", status=BulkSubmissionItemStatus.QUEUED),
        SimpleNamespace(youtube_id="bbbbbbbbbbb", status=BulkSubmissionItemStatus.QUEUED),
        SimpleNamespace(youtube_id="ccccccccccc", status=BulkSubmissionItemStatus.QUEUED),
    ]
    staged: list[str] = []

    async def fake_count(_db, _batch_id, _statuses):
        return 0

    async def fake_stage(_db, item):
        staged.append(item.youtube_id)
        return uuid4()

    class Scalars:
        def all(self):
            return items[:2]

    class ExecResult:
        def scalars(self):
            return Scalars()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=ExecResult())
    monkeypatch.setattr(bs, "_count_batch_status", fake_count)
    monkeypatch.setattr(bs, "_stage_item", fake_stage)

    fps = await bs.stage_next_bulk_items(db, batch_id)
    assert len(fps) == 2
    assert staged == ["aaaaaaaaaaa", "bbbbbbbbbbb"]


@pytest.mark.asyncio
async def test_stage_next_skips_when_window_full(monkeypatch):
    from app.services import bulk_submit as bs

    monkeypatch.setattr(bs.settings, "bulk_submit_staging_window", 10)

    async def fake_count(_db, _batch_id, _statuses):
        return 10

    db = AsyncMock()
    monkeypatch.setattr(bs, "_count_batch_status", fake_count)
    fps = await bs.stage_next_bulk_items(db, uuid4())
    assert fps == []
    db.execute.assert_not_called()


def test_open_queue_statuses_include_queued():
    from app.models import BulkSubmissionItemStatus
    from app.services.bulk_submit import _OPEN_QUEUE_STATUSES, _STAGING_STATUSES

    assert BulkSubmissionItemStatus.QUEUED in _OPEN_QUEUE_STATUSES
    assert BulkSubmissionItemStatus.QUEUED not in _STAGING_STATUSES
    assert BulkSubmissionItemStatus.READY in _STAGING_STATUSES


def test_staging_window_default():
    assert get_settings().bulk_submit_staging_window == 10
    assert get_settings().bulk_submit_max_playlist_items >= 2000


def test_normalize_bulk_defaults_strips_empty():
    from app.services.bulk_submit import normalize_bulk_defaults

    cleaned = normalize_bulk_defaults(
        {
            "commercial_type": "psa",
            "bumper_channel": "  ",
            "advertiser_name": "Acme",
            "tags": [" ", "promo", ""],
            "year": 1990,
            "decade": None,
        }
    )
    assert cleaned == {
        "commercial_type": "psa",
        "advertiser_name": "Acme",
        "tags": ["promo"],
        "year": 1990,
    }


def test_bulk_playlist_defaults_keeps_target_channel_for_general_ad():
    from app.schemas import BulkPlaylistDefaults

    defaults = BulkPlaylistDefaults(
        commercial_type="general_ad",
        target_channel="  ESPN  ",
    )
    assert defaults.target_channel == "ESPN"
    assert defaults.bumper_channel is None


def test_bulk_playlist_defaults_drops_target_channel_when_not_general_ad():
    from app.schemas import BulkPlaylistDefaults

    defaults = BulkPlaylistDefaults(
        commercial_type="psa",
        target_channel="ESPN",
    )
    assert defaults.target_channel is None


@pytest.mark.asyncio
async def test_cancel_bulk_batch_deletes_preview_fingerprints(monkeypatch):
    from app.services import bulk_submit as bs

    batch_id = uuid4()
    owner_id = uuid4()
    preview_fp_id = uuid4()
    attached_fp_id = uuid4()
    preview_fp = SimpleNamespace(id=preview_fp_id, edit_id=None)
    attached_fp = SimpleNamespace(id=attached_fp_id, edit_id=uuid4())
    batch = SimpleNamespace(
        id=batch_id,
        owner_id=owner_id,
        items=[
            SimpleNamespace(fingerprint_id=preview_fp_id),
            SimpleNamespace(fingerprint_id=attached_fp_id),
            SimpleNamespace(fingerprint_id=None),
        ],
    )
    deleted: list[object] = []

    async def fake_get_owner_batch(_db, _owner_id, _batch_id):
        return batch

    async def fake_get(_model, obj_id):
        if obj_id == preview_fp_id:
            return preview_fp
        if obj_id == attached_fp_id:
            return attached_fp
        return None

    db = AsyncMock()
    db.get = fake_get
    db.delete = AsyncMock(side_effect=lambda obj: deleted.append(obj))
    db.flush = AsyncMock()
    monkeypatch.setattr(bs, "get_owner_batch", fake_get_owner_batch)

    result = await bs.cancel_bulk_batch(db, owner_id, batch_id)

    assert result is batch
    assert batch in deleted
    assert preview_fp in deleted
    assert attached_fp not in deleted


@pytest.mark.asyncio
async def test_cancel_bulk_batch_missing_returns_none(monkeypatch):
    from app.services import bulk_submit as bs

    async def fake_get_owner_batch(_db, _owner_id, _batch_id):
        return None

    db = AsyncMock()
    monkeypatch.setattr(bs, "get_owner_batch", fake_get_owner_batch)
    assert await bs.cancel_bulk_batch(db, uuid4(), uuid4()) is None
    db.delete.assert_not_called()
