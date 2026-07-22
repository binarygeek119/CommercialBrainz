"""Tests for commercial metadata edit helpers."""

from app.services.commercial_metadata import metadata_snapshot_changed


def test_metadata_snapshot_detects_title_change():
    before = {"title": "Old spot", "products": ["Soda"]}
    after = {"title": "New spot", "products": ["Soda"]}
    assert metadata_snapshot_changed(before, after)


def test_metadata_snapshot_detects_commercial_type_change():
    before = {"title": "Spot", "commercial_type": "general_ad"}
    after = {"title": "Spot", "commercial_type": "psa"}
    assert metadata_snapshot_changed(before, after)


def test_metadata_snapshot_ignores_unchanged_products():
    state = {"title": "Spot", "products": ["Soda", "Chips"]}
    assert not metadata_snapshot_changed(state, dict(state))
