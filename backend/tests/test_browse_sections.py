"""Unit tests for browse shelf helpers."""

from app.services.browse import SECTION_SPECS, bumper_channel_is_major_network


def test_section_order_puts_needs_votes_first():
    assert SECTION_SPECS[0]["id"] == "needs_votes"
    ids = [s["id"] for s in SECTION_SPECS]
    assert ids[:3] == ["needs_votes", "newly_added", "updated"]
    assert "new_brands" in ids
    assert "updated_brands" in ids
    assert "new_stores" in ids
    assert "updated_stores" in ids
    assert "new_services" in ids
    assert "updated_services" in ids
    assert "new_events" in ids
    assert "updated_events" in ids
    assert "new_holidays" in ids
    assert "updated_holidays" in ids
    # Catalog shelves come before typed commercial video shelves.
    assert ids.index("new_brands") < ids.index("psa")
    assert ids.index("updated_holidays") < ids.index("psa")


def test_major_network_channel_matching():
    assert bumper_channel_is_major_network("Fox")
    assert bumper_channel_is_major_network("NBC")
    assert bumper_channel_is_major_network("Cartoon Network")
    assert bumper_channel_is_major_network("Nickelodeon")
    assert bumper_channel_is_major_network("Fox Kids")
    assert bumper_channel_is_major_network("Disney Channel")
    assert bumper_channel_is_major_network("PBS Kids")
    assert not bumper_channel_is_major_network("Xbox")
    assert not bumper_channel_is_major_network("ESPN")
    assert not bumper_channel_is_major_network(None)
    assert not bumper_channel_is_major_network("")
