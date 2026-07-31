"""Tests for Domain / Cloud VM donation fund matching and ledger math."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import DonationFund
from app.services import donate_funds as funds


def test_match_fund_exact_and_substring():
    assert funds.match_fund(funds.DOMAIN_MESSAGE) == DonationFund.DOMAIN
    assert funds.match_fund(funds.VM_MESSAGE) == DonationFund.CLOUD_VM
    assert (
        funds.match_fund(f"Thanks! {funds.DOMAIN_MESSAGE}") == DonationFund.DOMAIN
    )
    assert funds.match_fund(funds.VM_MESSAGE.upper()) == DonationFund.CLOUD_VM


def test_match_fund_rejects_empty_or_unrelated():
    assert funds.match_fund(None) is None
    assert funds.match_fund("") is None
    assert funds.match_fund("   ") is None
    assert funds.match_fund("General support for the site") is None


def test_parse_supporter_amount():
    assert funds.parse_supporter_amount(
        {"support_coffees": 3, "support_coffee_price": "5.00"}
    ) == Decimal("15.00")
    assert funds.parse_supporter_amount({}) == Decimal("0.00")


def test_is_refunded():
    assert funds.is_refunded({"is_refunded": "true"}) is True
    assert funds.is_refunded({"is_refunded": False}) is False
    assert funds.is_refunded({}) is False


def test_verify_webhook_signature(monkeypatch):
    monkeypatch.setattr(
        funds,
        "get_settings",
        lambda: SimpleNamespace(buymeacoffee_webhook_secret="test-secret"),
    )
    body = b'{"type":"donation.created"}'
    import hashlib
    import hmac

    sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert funds.verify_bmc_webhook_signature(body, sig) is True
    assert funds.verify_bmc_webhook_signature(body, "deadbeef") is False
    assert funds.verify_bmc_webhook_signature(body, None) is False


@pytest.mark.asyncio
async def test_ingest_skips_before_cutoff():
    cutoff = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    db = AsyncMock()
    # Should not query for existing when donated_at is before cutoff after match
    result = await funds.ingest_supporter(
        db,
        {
            "support_id": 1,
            "support_note": funds.DOMAIN_MESSAGE,
            "support_coffees": 1,
            "support_coffee_price": "5",
            "support_created_on": (cutoff - timedelta(days=1)).isoformat(),
            "support_currency": "USD",
        },
        tracking_started_at=cutoff,
    )
    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_inserts_new_and_dedups(monkeypatch):
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    donated = datetime(2026, 7, 31, 15, 0, tzinfo=UTC)

    class FakeResult:
        def __init__(self, row=None):
            self._row = row

        def scalar_one_or_none(self):
            return self._row

    class FakeDB:
        def __init__(self):
            self.added = []
            self._existing = None

        def add(self, obj):
            obj.id = uuid4()
            self.added.append(obj)
            self._existing = obj

        async def execute(self, _stmt):
            return FakeResult(self._existing)

        async def flush(self):
            return None

    db = FakeDB()
    raw = {
        "support_id": 42,
        "support_note": funds.VM_MESSAGE,
        "support_coffees": 2,
        "support_coffee_price": "5.00",
        "support_created_on": donated.isoformat(),
        "support_currency": "USD",
        "supporter_name": "Ada",
    }
    first = await funds.ingest_supporter(db, raw, tracking_started_at=cutoff)
    assert first is not None
    assert first.bmc_support_id == 42
    assert first.fund == DonationFund.CLOUD_VM
    assert Decimal(str(first.amount)) == Decimal("10.00")
    assert len(db.added) == 1

    second = await funds.ingest_supporter(
        db,
        {**raw, "support_coffees": 3},
        tracking_started_at=cutoff,
    )
    assert second is first
    assert Decimal(str(second.amount)) == Decimal("15.00")
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_balance_floors_at_zero(monkeypatch):
    monkeypatch.setattr(
        funds, "sum_raised", AsyncMock(return_value=Decimal("10.00"))
    )
    monkeypatch.setattr(
        funds, "sum_spent", AsyncMock(return_value=Decimal("25.00"))
    )
    snap = await funds.fund_snapshot(
        AsyncMock(),
        DonationFund.DOMAIN,
        {"domain": {"goal": 50}},
    )
    assert snap["raised"] == 10.0
    assert snap["spent"] == 25.0
    assert snap["balance"] == 0.0
    assert snap["goal"] == 50.0


@pytest.mark.asyncio
async def test_add_cost_rejects_non_positive():
    with pytest.raises(ValueError, match="greater than zero"):
        await funds.add_cost(
            AsyncMock(),
            fund=DonationFund.DOMAIN,
            amount=0,
            note=None,
            paid_at=None,
            created_by=None,
        )


@pytest.mark.asyncio
async def test_sync_requires_token(monkeypatch):
    monkeypatch.setattr(
        funds,
        "get_settings",
        lambda: SimpleNamespace(buymeacoffee_access_token=""),
    )
    monkeypatch.setattr(funds, "ensure_settings", AsyncMock(return_value=funds.default_settings_value()))
    with pytest.raises(ValueError, match="BUYMEACOFFEE_ACCESS_TOKEN"):
        await funds.sync_supporters(AsyncMock(), force=True)


@pytest.mark.asyncio
async def test_sync_supporters_ingests_pages(monkeypatch):
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    settings = funds.default_settings_value(now=cutoff)
    monkeypatch.setattr(
        funds,
        "get_settings",
        lambda: SimpleNamespace(buymeacoffee_access_token="tok"),
    )
    monkeypatch.setattr(funds, "ensure_settings", AsyncMock(return_value=settings))
    monkeypatch.setattr(funds, "_save_settings", AsyncMock())
    monkeypatch.setattr(
        funds,
        "admin_funds_payload",
        AsyncMock(return_value={"ok": True}),
    )

    ingested = []

    async def fake_ingest(db, raw, *, tracking_started_at):
        ingested.append(raw["support_id"])
        return MagicMock()

    monkeypatch.setattr(funds, "ingest_supporter", fake_ingest)

    pages = {
        1: {
            "last_page": 2,
            "data": [
                {
                    "support_id": 1,
                    "support_note": funds.DOMAIN_MESSAGE,
                    "support_coffees": 1,
                    "support_coffee_price": "5",
                    "support_created_on": "2026-07-15T00:00:00+00:00",
                }
            ],
        },
        2: {
            "last_page": 2,
            "data": [
                {
                    "support_id": 2,
                    "support_note": funds.VM_MESSAGE,
                    "support_coffees": 1,
                    "support_coffee_price": "5",
                    "support_created_on": "2026-07-16T00:00:00+00:00",
                }
            ],
        },
    }

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None, timeout=None):
            return FakeResponse(pages[params["page"]])

    monkeypatch.setattr(funds.httpx, "AsyncClient", lambda: FakeClient())

    result = await funds.sync_supporters(AsyncMock(), force=True)
    assert result == {"ok": True}
    assert ingested == [1, 2]
