"""Commercial metadata helpers for community edits."""

from __future__ import annotations

from app.models import Commercial

COMMERCIAL_METADATA_EDIT_KEYS = (
    "title",
    "year",
    "decade",
    "commercial_type",
    "bumper_channel",
    "campaign_name",
    "description",
    "products",
    "store_id",
    "service_id",
    "event_id",
    "holiday_id",
)


def commercial_to_state(commercial: Commercial) -> dict:
    state: dict = {
        "commercial_id": str(commercial.sbid),
        "title": commercial.title,
        "year": commercial.year,
        "decade": commercial.decade,
        "commercial_type": (
            commercial.commercial_type.value
            if commercial.commercial_type is not None
            else None
        ),
        "bumper_channel": commercial.bumper_channel,
        "campaign_name": commercial.campaign_name,
        "description": commercial.description,
        "advertiser_id": str(commercial.advertiser_id) if commercial.advertiser_id else None,
        "store_id": str(commercial.store_id) if commercial.store_id else None,
        "service_id": str(commercial.service_id) if commercial.service_id else None,
        "event_id": str(commercial.event_id) if commercial.event_id else None,
        "holiday_id": str(commercial.holiday_id) if commercial.holiday_id else None,
        "agency_id": str(commercial.agency_id) if commercial.agency_id else None,
        "products": [p.name for p in commercial.products],
    }
    return {k: v for k, v in state.items() if v not in (None, "", [])}


def metadata_snapshot_changed(before: dict, after: dict) -> bool:
    for key in COMMERCIAL_METADATA_EDIT_KEYS:
        if before.get(key) != after.get(key):
            return True
    return False
