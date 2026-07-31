"""Domain and Cloud VM donation fund tracking via Buy Me a Coffee notes."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import DonationFund, DonationFundCost, DonationFundEntry, SiteSetting, User

logger = logging.getLogger(__name__)

SETTINGS_KEY = "donate_funds"
BMC_SUPPORTERS_URL = "https://developers.buymeacoffee.com/api/v1/supporters"
SYNC_STALE_AFTER = timedelta(minutes=10)

DOMAIN_MESSAGE = "Donation for the CommercialBrainz domain"
VM_MESSAGE = "Donation for the CommercialBrainz cloud VM"

FUND_MESSAGES: dict[DonationFund, str] = {
    DonationFund.DOMAIN: DOMAIN_MESSAGE,
    DonationFund.CLOUD_VM: VM_MESSAGE,
}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def default_settings_value(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    return {
        "tracking_started_at": now.isoformat(),
        "domain": {"goal": 0},
        "cloud_vm": {"goal": 0},
        "last_sync_at": None,
        "last_sync_error": None,
    }


async def _get_setting_row(db: AsyncSession) -> SiteSetting | None:
    return await db.get(SiteSetting, SETTINGS_KEY)


async def ensure_settings(db: AsyncSession) -> dict[str, Any]:
    row = await _get_setting_row(db)
    if row is None:
        value = default_settings_value()
        row = SiteSetting(key=SETTINGS_KEY, value=value)
        db.add(row)
        await db.flush()
        return dict(value)
    value = dict(row.value or {})
    changed = False
    if not value.get("tracking_started_at"):
        value["tracking_started_at"] = datetime.now(UTC).isoformat()
        changed = True
    for key in ("domain", "cloud_vm"):
        bucket = value.get(key)
        if not isinstance(bucket, dict):
            value[key] = {"goal": 0}
            changed = True
        elif "goal" not in bucket:
            bucket = {**bucket, "goal": 0}
            value[key] = bucket
            changed = True
    if "last_sync_at" not in value:
        value["last_sync_at"] = None
        changed = True
    if "last_sync_error" not in value:
        value["last_sync_error"] = None
        changed = True
    if changed:
        row.value = value
        row.updated_at = datetime.now(UTC)
        await db.flush()
    return value


async def _save_settings(db: AsyncSession, value: dict[str, Any]) -> None:
    row = await _get_setting_row(db)
    if row is None:
        row = SiteSetting(key=SETTINGS_KEY, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)
    await db.flush()


def match_fund(support_note: str | None) -> DonationFund | None:
    """Match BMC 'Say something nice' note to a fund (case-insensitive contains)."""
    if not support_note or not str(support_note).strip():
        return None
    note = str(support_note).strip().lower()
    # Prefer longer / more specific match first if both somehow appear.
    for fund, message in (
        (DonationFund.CLOUD_VM, VM_MESSAGE),
        (DonationFund.DOMAIN, DOMAIN_MESSAGE),
    ):
        if message.lower() in note:
            return fund
    return None


def parse_supporter_amount(raw: dict[str, Any]) -> Decimal:
    coffees = raw.get("support_coffees") or 0
    price = raw.get("support_coffee_price") or "0"
    try:
        return (Decimal(str(coffees)) * Decimal(str(price))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def parse_supporter_donated_at(raw: dict[str, Any]) -> datetime | None:
    for key in ("support_created_on", "support_updated_on"):
        dt = _parse_iso(raw.get(key) if isinstance(raw.get(key), str) else None)
        if dt is not None:
            return dt
    return None


def is_refunded(raw: dict[str, Any]) -> bool:
    value = raw.get("is_refunded")
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def money(value: Decimal | float | int | str | None) -> float:
    try:
        return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


async def sum_raised(db: AsyncSession, fund: DonationFund) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(DonationFundEntry.amount), 0)).where(
            DonationFundEntry.fund == fund
        )
    )
    return Decimal(str(result.scalar_one()))


async def sum_spent(db: AsyncSession, fund: DonationFund) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(DonationFundCost.amount), 0)).where(
            DonationFundCost.fund == fund
        )
    )
    return Decimal(str(result.scalar_one()))


async def fund_snapshot(db: AsyncSession, fund: DonationFund, settings: dict[str, Any]) -> dict[str, Any]:
    key = fund.value
    bucket = settings.get(key) if isinstance(settings.get(key), dict) else {}
    goal = money(bucket.get("goal") if isinstance(bucket, dict) else 0)
    raised = money(await sum_raised(db, fund))
    spent = money(await sum_spent(db, fund))
    balance = max(0.0, round(raised - spent, 2))
    return {
        "goal": goal,
        "raised": raised,
        "spent": spent,
        "balance": balance,
    }


def sync_configured() -> bool:
    return bool(get_settings().buymeacoffee_access_token.strip())


async def public_funds_payload(
    db: AsyncSession,
    *,
    maybe_sync: bool = True,
) -> dict[str, Any]:
    settings = await ensure_settings(db)
    if maybe_sync and sync_configured():
        last = _parse_iso(
            settings.get("last_sync_at")
            if isinstance(settings.get("last_sync_at"), str)
            else None
        )
        if last is None or datetime.now(UTC) - last >= SYNC_STALE_AFTER:
            try:
                await sync_supporters(db, force=True)
                settings = await ensure_settings(db)
            except Exception as exc:  # noqa: BLE001 — surface via last_sync_error
                logger.warning("donate funds sync failed: %s", exc)
                settings = await ensure_settings(db)

    return {
        "domain": await fund_snapshot(db, DonationFund.DOMAIN, settings),
        "cloud_vm": await fund_snapshot(db, DonationFund.CLOUD_VM, settings),
        "tracking_started_at": settings.get("tracking_started_at"),
        "sync_configured": sync_configured(),
        "last_sync_at": settings.get("last_sync_at"),
    }


async def list_recent_entries(
    db: AsyncSession, *, limit: int = 25
) -> list[DonationFundEntry]:
    result = await db.execute(
        select(DonationFundEntry)
        .order_by(DonationFundEntry.donated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_recent_costs(db: AsyncSession, *, limit: int = 25) -> list[DonationFundCost]:
    result = await db.execute(
        select(DonationFundCost).order_by(DonationFundCost.paid_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def admin_funds_payload(db: AsyncSession) -> dict[str, Any]:
    settings = await ensure_settings(db)
    public = await public_funds_payload(db, maybe_sync=False)
    entries = await list_recent_entries(db)
    costs = await list_recent_costs(db)
    return {
        **public,
        "last_sync_error": settings.get("last_sync_error"),
        "entries": [
            {
                "id": str(e.id),
                "fund": e.fund.value,
                "bmc_support_id": e.bmc_support_id,
                "amount": money(e.amount),
                "currency": e.currency,
                "support_note": e.support_note,
                "supporter_name": e.supporter_name,
                "donated_at": e.donated_at.isoformat() if e.donated_at else None,
            }
            for e in entries
        ],
        "costs": [
            {
                "id": str(c.id),
                "fund": c.fund.value,
                "amount": money(c.amount),
                "note": c.note,
                "paid_at": c.paid_at.isoformat() if c.paid_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in costs
        ],
    }


async def set_goals(
    db: AsyncSession,
    *,
    domain_goal: float,
    cloud_vm_goal: float,
) -> dict[str, Any]:
    if domain_goal < 0 or cloud_vm_goal < 0:
        raise ValueError("Goals must be non-negative")
    settings = await ensure_settings(db)
    settings["domain"] = {"goal": money(domain_goal)}
    settings["cloud_vm"] = {"goal": money(cloud_vm_goal)}
    await _save_settings(db, settings)
    return await admin_funds_payload(db)


async def add_cost(
    db: AsyncSession,
    *,
    fund: DonationFund,
    amount: float,
    note: str | None,
    paid_at: datetime | None,
    created_by: User | None,
) -> DonationFundCost:
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    when = paid_at or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    row = DonationFundCost(
        fund=fund,
        amount=money(amount),
        note=(note or "").strip() or None,
        paid_at=when.astimezone(UTC),
        created_by_id=created_by.id if created_by else None,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_cost(db: AsyncSession, cost_id: UUID) -> bool:
    row = await db.get(DonationFundCost, cost_id)
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True


async def _fetch_supporters_page(
    client: httpx.AsyncClient, token: str, page: int
) -> dict[str, Any]:
    response = await client.get(
        BMC_SUPPORTERS_URL,
        params={"page": page},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


async def ingest_supporter(
    db: AsyncSession,
    raw: dict[str, Any],
    *,
    tracking_started_at: datetime,
) -> DonationFundEntry | None:
    """Upsert a matched supporter into the ledger. Returns row if inserted/kept."""
    if is_refunded(raw):
        support_id = raw.get("support_id")
        if support_id is not None:
            existing = await db.execute(
                select(DonationFundEntry).where(
                    DonationFundEntry.bmc_support_id == int(support_id)
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                await db.delete(row)
                await db.flush()
        return None

    fund = match_fund(raw.get("support_note") if isinstance(raw.get("support_note"), str) else None)
    if fund is None:
        return None

    donated_at = parse_supporter_donated_at(raw)
    if donated_at is None:
        return None
    if donated_at < tracking_started_at:
        return None

    support_id = raw.get("support_id")
    if support_id is None:
        return None
    support_id = int(support_id)
    amount = parse_supporter_amount(raw)
    if amount <= 0:
        return None

    existing = await db.execute(
        select(DonationFundEntry).where(DonationFundEntry.bmc_support_id == support_id)
    )
    row = existing.scalar_one_or_none()
    currency = str(raw.get("support_currency") or "USD")[:16]
    note = raw.get("support_note") if isinstance(raw.get("support_note"), str) else None
    name = raw.get("supporter_name") or raw.get("payer_name")
    if isinstance(name, str):
        name = name[:255]
    else:
        name = None

    if row is None:
        row = DonationFundEntry(
            fund=fund,
            bmc_support_id=support_id,
            amount=amount,
            currency=currency,
            support_note=note,
            supporter_name=name,
            donated_at=donated_at,
        )
        db.add(row)
    else:
        row.fund = fund
        row.amount = amount
        row.currency = currency
        row.support_note = note
        row.supporter_name = name
        row.donated_at = donated_at
    await db.flush()
    return row


async def sync_supporters(db: AsyncSession, *, force: bool = False) -> dict[str, Any]:
    settings = await ensure_settings(db)
    token = get_settings().buymeacoffee_access_token.strip()
    if not token:
        raise ValueError("BUYMEACOFFEE_ACCESS_TOKEN is not configured")

    if not force:
        last = _parse_iso(
            settings.get("last_sync_at")
            if isinstance(settings.get("last_sync_at"), str)
            else None
        )
        if last is not None and datetime.now(UTC) - last < SYNC_STALE_AFTER:
            return await admin_funds_payload(db)

    tracking = _parse_iso(
        settings.get("tracking_started_at")
        if isinstance(settings.get("tracking_started_at"), str)
        else None
    )
    if tracking is None:
        tracking = datetime.now(UTC)
        settings["tracking_started_at"] = tracking.isoformat()

    inserted_or_updated = 0
    try:
        async with httpx.AsyncClient() as client:
            page = 1
            last_page = 1
            while page <= last_page:
                payload = await _fetch_supporters_page(client, token, page)
                last_page = int(payload.get("last_page") or 1)
                data = payload.get("data") or []
                if not isinstance(data, list):
                    break
                for raw in data:
                    if not isinstance(raw, dict):
                        continue
                    row = await ingest_supporter(
                        db, raw, tracking_started_at=tracking
                    )
                    if row is not None:
                        inserted_or_updated += 1
                page += 1
        settings["last_sync_at"] = datetime.now(UTC).isoformat()
        settings["last_sync_error"] = None
        await _save_settings(db, settings)
    except Exception as exc:
        settings["last_sync_error"] = str(exc)[:500]
        await _save_settings(db, settings)
        raise

    logger.info("donate funds sync complete; touched=%s", inserted_or_updated)
    return await admin_funds_payload(db)


def verify_bmc_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = get_settings().buymeacoffee_webhook_secret.strip()
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, signature.strip())
    except (TypeError, ValueError):
        return False


WEBHOOK_SYNC_EVENTS = frozenset(
    {
        "donation.created",
        "donation.refunded",
    }
)
