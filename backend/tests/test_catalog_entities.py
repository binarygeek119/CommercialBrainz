"""Tests for catalog entities (stores/services/events/holidays)."""

from uuid import uuid4

from app.models import Edit, EditStatus, EditType
from app.services.catalog import (
    STORE,
    metadata_snapshot_changed,
)
from app.services.holiday_dates import parse_holiday_date_text
from app.services.user_profile import edit_summary_title


def test_parse_holiday_full_mdy():
    parsed = parse_holiday_date_text("10/31/1999")
    assert parsed.date_text == "10/31/1999"
    assert parsed.year == 1999
    assert parsed.month == 10
    assert parsed.day == 31


def test_parse_holiday_md_only():
    parsed = parse_holiday_date_text("10/31")
    assert parsed.year is None
    assert parsed.month == 10
    assert parsed.day == 31


def test_parse_holiday_name_year():
    parsed = parse_holiday_date_text("Halloween - 1999")
    assert parsed.year == 1999
    assert parsed.month is None
    assert parsed.day is None


def test_parse_holiday_name_only():
    parsed = parse_holiday_date_text("Halloween")
    assert parsed.year is None
    assert parsed.month is None
    assert parsed.day is None
    assert parsed.date_text == "Halloween"


def test_parse_holiday_year_only():
    parsed = parse_holiday_date_text("2002")
    assert parsed.year == 2002


def test_catalog_metadata_snapshot_detects_store_type_change():
    before = {"name": "Acme Mart", "store_type": "grocery"}
    after = {"name": "Acme Mart", "store_type": "department"}
    assert metadata_snapshot_changed(STORE, before, after)


def test_catalog_metadata_snapshot_ignores_identical():
    state = {"name": "Acme Mart", "store_type": "grocery", "aliases": ["Acme"]}
    assert not metadata_snapshot_changed(STORE, state, dict(state))


def test_commercial_metadata_detects_store_id_change():
    from app.services.commercial_metadata import metadata_snapshot_changed as commercial_changed

    before = {"title": "Spot", "store_id": str(uuid4())}
    after = {"title": "Spot", "store_id": str(uuid4())}
    assert commercial_changed(before, after)


def test_catalog_vote_threshold_matches_brand():
    from app.services import EditService

    class _Fake:
        edit_type = EditType.CREATE_STORE

    assert EditService._vote_threshold(_Fake()) == 10


def _edit(*, edit_type: EditType, after_state: dict, entity_type: str = "store") -> Edit:
    return Edit(
        edit_type=edit_type,
        status=EditStatus.OPEN,
        entity_type=entity_type,
        after_state=after_state,
        editor_id=None,  # type: ignore[arg-type]
        expires_at=None,  # type: ignore[arg-type]
    )


def test_edit_summary_title_create_store():
    edit = _edit(
        edit_type=EditType.CREATE_STORE,
        after_state={"name": "Corner Shop"},
        entity_type="store",
    )
    assert edit_summary_title(edit) == "Corner Shop"


def test_edit_summary_title_edit_holiday():
    edit = _edit(
        edit_type=EditType.EDIT_HOLIDAY,
        after_state={"name": "Halloween"},
        entity_type="holiday",
    )
    assert edit_summary_title(edit) == "Halloween"


def test_edit_summary_title_add_event_logo():
    edit = _edit(
        edit_type=EditType.ADD_EVENT_LOGO,
        after_state={"label": "2024 lockup"},
        entity_type="event",
    )
    assert edit_summary_title(edit) == "2024 lockup"
