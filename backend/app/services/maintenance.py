"""Site maintenance schedule, manual gate, and login announcements."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SiteSetting, UserAnnouncementAck

ANNOUNCEMENT_KEY = "login_announcement"
SCHEDULE_KEY = "maintenance_schedule"
MANUAL_KEY = "maintenance_manual"

# How far ahead to surface upcoming windows in the public banner.
UPCOMING_HORIZON = timedelta(hours=72)
# Keep finished windows briefly for audit, then prune.
PAST_RETENTION = timedelta(days=7)


async def _get_setting(db: AsyncSession, key: str) -> SiteSetting | None:
    return await db.get(SiteSetting, key)


async def _set_setting(db: AsyncSession, key: str, value: dict[str, Any]) -> SiteSetting:
    row = await _get_setting(db, key)
    if row is None:
        row = SiteSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


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


def _window_dict(raw: dict[str, Any]) -> dict[str, Any] | None:
    starts = _parse_iso(raw.get("starts_at") if isinstance(raw.get("starts_at"), str) else None)
    ends = _parse_iso(raw.get("ends_at") if isinstance(raw.get("ends_at"), str) else None)
    if starts is None or ends is None or ends <= starts:
        return None
    wid = str(raw.get("id") or uuid.uuid4())
    message = (raw.get("message") or "").strip() or (
        f"The site will be offline for maintenance from {starts.isoformat()} "
        f"until {ends.isoformat()}."
    )
    return {
        "id": wid,
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "message": message,
    }


def active_window(
    windows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    now = now or datetime.now(UTC)
    for raw in windows:
        starts = _parse_iso(raw.get("starts_at"))
        ends = _parse_iso(raw.get("ends_at"))
        if starts is None or ends is None:
            continue
        if starts <= now < ends:
            return raw
    return None


def upcoming_windows(
    windows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    horizon: timedelta = UPCOMING_HORIZON,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    cutoff = now + horizon
    out: list[dict[str, Any]] = []
    for raw in windows:
        starts = _parse_iso(raw.get("starts_at"))
        ends = _parse_iso(raw.get("ends_at"))
        if starts is None or ends is None:
            continue
        if now < starts <= cutoff:
            out.append(raw)
    out.sort(key=lambda w: w.get("starts_at") or "")
    return out


def prune_windows(
    windows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    keep: list[dict[str, Any]] = []
    for raw in windows:
        ends = _parse_iso(raw.get("ends_at"))
        if ends is None:
            continue
        if ends + PAST_RETENTION >= now:
            keep.append(raw)
    return keep


async def get_announcement(db: AsyncSession) -> dict[str, Any]:
    row = await _get_setting(db, ANNOUNCEMENT_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {
        "id": value.get("id"),
        "enabled": bool(value.get("enabled")),
        "title": (value.get("title") or "").strip() or "Announcement",
        "body": (value.get("body") or "").strip(),
        "updated_at": value.get("updated_at"),
    }


async def set_announcement(
    db: AsyncSession,
    *,
    enabled: bool,
    title: str,
    body: str,
    bump_id: bool = True,
) -> dict[str, Any]:
    current = await get_announcement(db)
    announcement_id = current.get("id") if not bump_id and current.get("id") else str(uuid.uuid4())
    # Always bump id when content/enable changes so users must re-ack.
    if bump_id:
        announcement_id = str(uuid.uuid4())
    payload = {
        "id": announcement_id,
        "enabled": enabled,
        "title": title.strip() or "Announcement",
        "body": body.strip(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    await _set_setting(db, ANNOUNCEMENT_KEY, payload)
    return payload


async def get_manual_maintenance(db: AsyncSession) -> dict[str, Any]:
    row = await _get_setting(db, MANUAL_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    return {
        "enabled": bool(value.get("enabled")),
        "message": (value.get("message") or "").strip()
        or "The site is temporarily offline for maintenance. Please come back later.",
    }


async def set_manual_maintenance(
    db: AsyncSession,
    *,
    enabled: bool,
    message: str | None = None,
) -> dict[str, Any]:
    payload = {
        "enabled": enabled,
        "message": (message or "").strip()
        or "The site is temporarily offline for maintenance. Please come back later.",
    }
    await _set_setting(db, MANUAL_KEY, payload)
    return payload


async def get_schedule(db: AsyncSession) -> dict[str, Any]:
    row = await _get_setting(db, SCHEDULE_KEY)
    value = row.value if row and isinstance(row.value, dict) else {}
    windows_raw = value.get("windows") if isinstance(value.get("windows"), list) else []
    windows: list[dict[str, Any]] = []
    for item in windows_raw:
        if isinstance(item, dict):
            normalized = _window_dict(item)
            if normalized:
                windows.append(normalized)
    windows = prune_windows(windows)
    return {"windows": windows}


async def set_schedule(
    db: AsyncSession,
    windows: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for item in windows:
        if not isinstance(item, dict):
            raise ValueError("Each window must be an object")
        parsed = _window_dict(item)
        if parsed is None:
            raise ValueError("Each window needs starts_at < ends_at (ISO-8601)")
        normalized.append(parsed)
    normalized = prune_windows(normalized)
    payload = {"windows": normalized}
    await _set_setting(db, SCHEDULE_KEY, payload)
    return payload


async def add_schedule_window(
    db: AsyncSession,
    *,
    starts_at: str,
    ends_at: str,
    message: str = "",
) -> dict[str, Any]:
    schedule = await get_schedule(db)
    windows = list(schedule["windows"])
    parsed = _window_dict(
        {"starts_at": starts_at, "ends_at": ends_at, "message": message, "id": str(uuid.uuid4())}
    )
    if parsed is None:
        raise ValueError("Window needs starts_at < ends_at (ISO-8601)")
    windows.append(parsed)
    return await set_schedule(db, windows)


async def remove_schedule_window(db: AsyncSession, window_id: str) -> dict[str, Any]:
    schedule = await get_schedule(db)
    windows = [w for w in schedule["windows"] if w.get("id") != window_id]
    return await set_schedule(db, windows)


def build_maintenance_state(
    *,
    manual: dict[str, Any],
    windows: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if manual.get("enabled"):
        return {
            "active": True,
            "reason": "manual",
            "message": manual.get("message"),
            "window": None,
            "upcoming": upcoming_windows(windows, now=now),
        }
    current = active_window(windows, now=now)
    if current:
        return {
            "active": True,
            "reason": "scheduled",
            "message": current.get("message"),
            "window": current,
            "upcoming": upcoming_windows(windows, now=now),
        }
    return {
        "active": False,
        "reason": None,
        "message": None,
        "window": None,
        "upcoming": upcoming_windows(windows, now=now),
    }


async def build_site_status(db: AsyncSession, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    announcement = await get_announcement(db)
    manual = await get_manual_maintenance(db)
    schedule = await get_schedule(db)
    # Persist pruned schedule when needed
    await _set_setting(db, SCHEDULE_KEY, schedule)
    maintenance = build_maintenance_state(
        manual=manual,
        windows=schedule["windows"],
        now=now,
    )
    public_announcement = None
    if announcement.get("enabled") and announcement.get("body"):
        public_announcement = {
            "id": announcement.get("id"),
            "title": announcement.get("title"),
            "body": announcement.get("body"),
        }
    return {
        "maintenance": maintenance,
        "announcement": public_announcement,
    }


async def get_pending_announcement_for_user(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any] | None:
    announcement = await get_announcement(db)
    if not announcement.get("enabled") or not announcement.get("body"):
        return None
    announcement_id = announcement.get("id")
    if not announcement_id:
        return None
    existing = await db.scalar(
        select(UserAnnouncementAck).where(
            UserAnnouncementAck.user_id == user_id,
            UserAnnouncementAck.announcement_id == str(announcement_id),
        )
    )
    if existing is not None:
        return None
    return {
        "id": announcement_id,
        "title": announcement.get("title"),
        "body": announcement.get("body"),
    }


async def ack_announcement_for_user(
    db: AsyncSession,
    user_id: UUID,
    announcement_id: str | None = None,
) -> dict[str, Any]:
    announcement = await get_announcement(db)
    target_id = announcement_id or announcement.get("id")
    if not target_id:
        raise ValueError("No announcement to acknowledge")
    if announcement.get("id") and str(announcement["id"]) != str(target_id):
        # Stale id — still record so client can dismiss; no error.
        pass
    existing = await db.scalar(
        select(UserAnnouncementAck).where(
            UserAnnouncementAck.user_id == user_id,
            UserAnnouncementAck.announcement_id == str(target_id),
        )
    )
    if existing is None:
        db.add(
            UserAnnouncementAck(
                user_id=user_id,
                announcement_id=str(target_id),
                acked_at=datetime.now(UTC),
            )
        )
        await db.flush()
    return {"acked": True, "announcement_id": str(target_id)}
