"""Commercial metadata helpers for community edits."""

from __future__ import annotations

from app.models import Commercial

COMMERCIAL_METADATA_EDIT_KEYS = (
    "title",
    "year",
    "decade",
    "commercial_type",
    "campaign_name",
    "description",
    "products",
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
        "campaign_name": commercial.campaign_name,
        "description": commercial.description,
        "advertiser_id": str(commercial.advertiser_id) if commercial.advertiser_id else None,
        "agency_id": str(commercial.agency_id) if commercial.agency_id else None,
        "products": [p.name for p in commercial.products],
    }
    return {k: v for k, v in state.items() if v not in (None, "", [])}


def metadata_snapshot_changed(before: dict, after: dict) -> bool:
    for key in COMMERCIAL_METADATA_EDIT_KEYS:
        if before.get(key) != after.get(key):
            return True
    return False
