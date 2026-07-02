"""Tests for logo metadata edit helpers."""

from app.services.logo_metadata import logo_to_state, metadata_snapshot_changed


class _Logo:
    id = "00000000-0000-4000-8000-000000000001"
    advertiser_id = "00000000-0000-4000-8000-000000000002"
    image_url = "/api/v1/media/logos/example.webp"
    label = "2019 wordmark"
    year = 2019
    month = 3
    event = None
    notes = "Source: brand guidelines"


def test_logo_to_state():
    state = logo_to_state(_Logo())  # type: ignore[arg-type]
    assert state["label"] == "2019 wordmark"
    assert state["year"] == 2019
    assert state["month"] == 3
    assert state["image_url"].endswith("example.webp")


def test_metadata_snapshot_changed_detects_label_update():
    before = {"label": "Old", "year": 2019}
    after = {"label": "New", "year": 2019}
    assert metadata_snapshot_changed(before, after)


def test_metadata_snapshot_changed_ignores_unchanged():
    state = {"label": "Same", "year": 2019, "notes": None}
    assert not metadata_snapshot_changed(state, dict(state))
