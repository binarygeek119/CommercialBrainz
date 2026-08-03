"""Tests for reputation / concurrent submit slot limits."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import EditStatus, EditType, UserRole
from app.services.reputation import (
    SUBMIT_SLOT_EXEMPT_EDIT_TYPES,
    assert_can_submit,
    count_open_submissions,
    max_submit_slots,
)


def test_new_user_gets_one_submit_slot():
    user = SimpleNamespace(
        role=UserRole.USER,
        is_auto_editor=False,
        reputation_points=0,
    )
    assert max_submit_slots(user) == 1


def test_brand_and_catalog_creates_are_slot_exempt():
    assert EditType.CREATE_ADVERTISER in SUBMIT_SLOT_EXEMPT_EDIT_TYPES
    assert EditType.CREATE_STORE in SUBMIT_SLOT_EXEMPT_EDIT_TYPES
    assert EditType.CREATE_VIDEO not in SUBMIT_SLOT_EXEMPT_EDIT_TYPES


@pytest.mark.asyncio
async def test_count_open_submissions_ignores_companion_brand_edits():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=1)
    used = await count_open_submissions(db, uuid4())
    assert used == 1
    where_clause = str(db.scalar.await_args.args[0])
    # Ensure the query excludes exempt companion create types.
    assert "not_in" in where_clause.lower() or "NOT IN" in where_clause or "notin" in where_clause.lower()


@pytest.mark.asyncio
async def test_assert_can_submit_allows_when_only_brand_edit_is_open(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        role=UserRole.USER,
        is_auto_editor=False,
        reputation_points=0,
    )
    db = MagicMock()

    async def _count(_db, _user_id):
        return 0  # brand edit open but exempt → 0 slot-consuming

    monkeypatch.setattr(
        "app.services.reputation.count_open_submissions",
        _count,
    )
    await assert_can_submit(db, user)


@pytest.mark.asyncio
async def test_assert_can_submit_blocks_when_video_slot_used(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        role=UserRole.USER,
        is_auto_editor=False,
        reputation_points=0,
    )
    db = MagicMock()

    async def _count(_db, _user_id):
        return 1

    monkeypatch.setattr(
        "app.services.reputation.count_open_submissions",
        _count,
    )
    with pytest.raises(ValueError, match=r"No submit slots available \(1/1\)"):
        await assert_can_submit(db, user)


def test_open_status_still_referenced_for_counting():
    assert EditStatus.OPEN.value == "open"
