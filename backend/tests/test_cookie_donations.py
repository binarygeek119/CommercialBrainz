"""Tests for community YouTube cookie donation backlog."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import CookieDonationStatus


@pytest.mark.asyncio
async def test_submit_queues_when_cookies_already_active(monkeypatch):
    from app.services import cookie_donations as cd

    monkeypatch.setattr(cd, "resolve_cookies_path", lambda: MagicMock())
    monkeypatch.setattr(cd, "validate_cookies_text", lambda text: text)
    monkeypatch.setattr(cd, "encrypt_cookies", lambda text: f"cbenc1:CIPHER:{text[:20]}")

    class FakeDB:
        def add(self, obj):
            obj.id = uuid4()
            obj.status = CookieDonationStatus.PENDING

        async def flush(self):
            return None

    row = await cd.submit_cookie_donation(
        FakeDB(),
        cookies="# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n",
        agreement_accepted=True,
        donor_note="dummy account",
    )
    assert row.status == CookieDonationStatus.PENDING
    assert row.agreement_accepted is True
    assert row.donor_note == "dummy account"
    assert row.cookies_text.startswith("cbenc1:")


@pytest.mark.asyncio
async def test_submit_requires_agreement():
    from app.services import cookie_donations as cd

    with pytest.raises(ValueError, match="agreement"):
        await cd.submit_cookie_donation(
            AsyncMock(),
            cookies="# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n",
            agreement_accepted=False,
        )


@pytest.mark.asyncio
async def test_submit_activates_when_no_active_file(monkeypatch):
    from app.services import cookie_donations as cd

    monkeypatch.setattr(cd, "resolve_cookies_path", lambda: None)
    monkeypatch.setattr(cd, "validate_cookies_text", lambda text: text)
    monkeypatch.setattr(cd, "encrypt_cookies", lambda text: f"cbenc1:{text}")

    async def fake_activate(db, row):
        row.status = CookieDonationStatus.ACTIVE
        return row

    monkeypatch.setattr(cd, "activate_donation", fake_activate)

    class FakeDB:
        def add(self, obj):
            obj.id = uuid4()
            obj.status = CookieDonationStatus.PENDING

        async def flush(self):
            return None

    row = await cd.submit_cookie_donation(
        FakeDB(),
        cookies="# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tx\n",
        agreement_accepted=True,
    )
    assert row.status == CookieDonationStatus.ACTIVE


@pytest.mark.asyncio
async def test_rotate_exhausted_to_next(monkeypatch):
    from app.services import cookie_donations as cd

    active = SimpleNamespace(
        id=uuid4(),
        status=CookieDonationStatus.ACTIVE,
        exhausted_at=None,
        updated_at=None,
    )
    pending = SimpleNamespace(
        id=uuid4(),
        status=CookieDonationStatus.PENDING,
        cookies_text="next",
        activated_at=None,
        exhausted_at=None,
        updated_at=None,
    )

    class Scalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class ExecResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return Scalars(self._rows)

    class FakeDB:
        async def execute(self, _query):
            return ExecResult([active])

        async def flush(self):
            return None

    async def fake_next(_db):
        pending.status = CookieDonationStatus.ACTIVE
        return pending

    monkeypatch.setattr(cd, "activate_next_pending", fake_next)

    nxt = await cd.rotate_exhausted_to_next(FakeDB())
    assert active.status == CookieDonationStatus.EXHAUSTED
    assert active.exhausted_at is not None
    assert nxt is pending
    assert pending.status == CookieDonationStatus.ACTIVE


def test_donation_public_dict_omits_cookies():
    from app.services.cookie_donations import donation_public_dict

    row = SimpleNamespace(
        id=uuid4(),
        status=CookieDonationStatus.PENDING,
        size_bytes=12,
        agreement_accepted=True,
        donor_note="hi",
        activated_at=None,
        exhausted_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        cookies_text="SECRET",
    )
    public = donation_public_dict(row)
    assert "cookies_text" not in public
    assert "SECRET" not in str(public.values())
    assert public["status"] == "pending"
