"""Logo metadata helpers for community edits."""

from __future__ import annotations

from app.models import AdvertiserLogo

LOGO_METADATA_EDIT_KEYS = ("label", "year", "month", "event", "notes")


def logo_to_state(logo: AdvertiserLogo) -> dict:
    state: dict = {
        "logo_id": str(logo.id),
        "advertiser_id": str(logo.advertiser_id),
        "image_url": logo.image_url,
        "label": logo.label,
        "year": logo.year,
        "month": logo.month,
        "event": logo.event,
        "notes": logo.notes,
    }
    return {k: v for k, v in state.items() if v not in (None, "")}


def metadata_snapshot_changed(before: dict, after: dict) -> bool:
    for key in LOGO_METADATA_EDIT_KEYS:
        if before.get(key) != after.get(key):
            return True
    return False
