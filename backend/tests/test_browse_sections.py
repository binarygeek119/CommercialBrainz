"""Unit tests for browse shelf helpers."""

from app.services.browse import SECTION_SPECS, bumper_channel_is_major_network


def test_section_order_puts_needs_votes_first():
    assert SECTION_SPECS[0]["id"] == "needs_votes"
    ids = [s["id"] for s in SECTION_SPECS]
    assert ids == [
        "needs_votes",
        "newly_added",
        "updated",
        "psa",
        "general_ad",
        "service",
        "store",
        "bumper",
        "channel_commercial",
    ]


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
