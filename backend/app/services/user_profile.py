"""Public user profile helpers."""

from __future__ import annotations

from app.models import Edit


def edit_summary_title(edit: Edit) -> str:
    state = edit.after_state or {}
    edit_type = edit.edit_type.value

    if edit_type == "create_advertiser":
        return str(state.get("name") or "New brand")
    if edit_type == "add_advertiser_logo":
        return str(state.get("label") or "Brand logo version")
    if edit_type == "edit_advertiser" and state.get("logo_url"):
        return "Brand logo"
    if edit_type == "edit_advertiser":
        return str(state.get("name") or "Brand metadata")
    if edit_type == "edit_commercial":
        return str(state.get("title") or "Commercial metadata")
    if edit_type == "edit_video" and state.get("thumbnail_url"):
        return "Custom thumbnail"

    commercial = state.get("commercial")
    if isinstance(commercial, dict) and commercial.get("title"):
        return str(commercial["title"])
    if state.get("title"):
        return str(state["title"])
    return edit.entity_type or edit_type.replace("_", " ")
