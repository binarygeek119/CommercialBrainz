"""Helpers for the reserved was-bulk-imported provenance marker."""

from __future__ import annotations

from app.models import BULK_IMPORTED_TAG, Commercial, User
from app.auth.security import user_can_see_bulk_import_marker


def normalize_user_tags(tags: list[str] | None) -> list[str]:
    """Lowercase/trim tags and strip the reserved system tag from user input."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        tag = str(raw).strip().lower()
        if not tag or tag == BULK_IMPORTED_TAG or tag in seen:
            continue
        seen.add(tag)
        cleaned.append(tag)
    return cleaned


def ensure_bulk_imported_tag(tags: list[str] | None) -> list[str]:
    base = normalize_user_tags(tags)
    if BULK_IMPORTED_TAG not in base:
        base.append(BULK_IMPORTED_TAG)
    return base


def filter_tags_for_viewer(tags: list[str], viewer: User | None) -> list[str]:
    if user_can_see_bulk_import_marker(viewer):
        return list(tags)
    return [t for t in tags if t != BULK_IMPORTED_TAG]


def commercial_was_bulk_imported_for_viewer(
    commercial: Commercial | None, viewer: User | None
) -> bool | None:
    """Return flag for privileged viewers; omit (None) for everyone else."""
    if not commercial or not user_can_see_bulk_import_marker(viewer):
        return None
    return bool(commercial.was_bulk_imported)
