"""Tests for public user profile helpers."""

from app.models import Edit, EditStatus, EditType
from app.services.user_profile import edit_summary_title


def _edit(*, edit_type: EditType, after_state: dict, entity_type: str = "video") -> Edit:
    return Edit(
        edit_type=edit_type,
        status=EditStatus.OPEN,
        entity_type=entity_type,
        after_state=after_state,
        editor_id=None,  # type: ignore[arg-type]
        expires_at=None,  # type: ignore[arg-type]
    )


def test_edit_summary_title_create_advertiser():
    edit = _edit(edit_type=EditType.CREATE_ADVERTISER, after_state={"name": "Acme Corp"}, entity_type="advertiser")
    assert edit_summary_title(edit) == "Acme Corp"


def test_edit_summary_title_edit_commercial():
    edit = _edit(
        edit_type=EditType.EDIT_COMMERCIAL,
        after_state={"title": "Holiday Spot"},
        entity_type="commercial",
    )
    assert edit_summary_title(edit) == "Holiday Spot"


def test_edit_summary_title_create_video_with_commercial():
    edit = _edit(
        edit_type=EditType.CREATE_VIDEO,
        after_state={"commercial": {"title": "Summer Sale"}},
        entity_type="video",
    )
    assert edit_summary_title(edit) == "Summer Sale"
