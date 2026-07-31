"""Tests for maintenance schedule / announcement helpers and edge gate logic."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.maintenance import (
    active_window,
    build_maintenance_state,
    prune_windows,
    upcoming_windows,
)

ROOT = Path(__file__).resolve().parents[2]
MAINT_DIR = ROOT / "infra" / "maintenance"
if str(MAINT_DIR) not in sys.path:
    sys.path.insert(0, str(MAINT_DIR))

from gate import (  # noqa: E402
    decide_gate,
    deploy_flag_active,
    render_maintenance_html,
    should_always_pass,
)


def test_active_window_boundaries():
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    windows = [
        {
            "id": "a",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "message": "now",
        },
        {
            "id": "b",
            "starts_at": (now + timedelta(hours=2)).isoformat(),
            "ends_at": (now + timedelta(hours=3)).isoformat(),
            "message": "later",
        },
    ]
    current = active_window(windows, now=now)
    assert current is not None
    assert current["id"] == "a"
    assert active_window(windows, now=now + timedelta(hours=5)) is None


def test_upcoming_within_horizon():
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    windows = [
        {
            "id": "soon",
            "starts_at": (now + timedelta(hours=6)).isoformat(),
            "ends_at": (now + timedelta(hours=8)).isoformat(),
            "message": "soon",
        },
        {
            "id": "far",
            "starts_at": (now + timedelta(days=10)).isoformat(),
            "ends_at": (now + timedelta(days=10, hours=2)).isoformat(),
            "message": "far",
        },
    ]
    upcoming = upcoming_windows(windows, now=now, horizon=timedelta(hours=72))
    assert [w["id"] for w in upcoming] == ["soon"]


def test_prune_drops_old_windows():
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    windows = [
        {
            "id": "old",
            "starts_at": (now - timedelta(days=20)).isoformat(),
            "ends_at": (now - timedelta(days=19)).isoformat(),
            "message": "old",
        },
        {
            "id": "keep",
            "starts_at": (now - timedelta(days=1)).isoformat(),
            "ends_at": (now - timedelta(hours=1)).isoformat(),
            "message": "keep",
        },
    ]
    kept = prune_windows(windows, now=now)
    assert [w["id"] for w in kept] == ["keep"]


def test_build_maintenance_prefers_manual():
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    windows = [
        {
            "id": "a",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "message": "scheduled",
        }
    ]
    state = build_maintenance_state(
        manual={"enabled": True, "message": "manual now"},
        windows=windows,
        now=now,
    )
    assert state["active"] is True
    assert state["reason"] == "manual"
    assert state["message"] == "manual now"


def test_gate_deploy_flag(tmp_path: Path):
    assert deploy_flag_active(tmp_path) is False
    (tmp_path / "UPDATE_IN_PROGRESS").write_text("")
    assert deploy_flag_active(tmp_path) is True
    decision = decide_gate(
        flag_active=True,
        status={"maintenance": {"active": False}},
        status_fetch_ok=True,
    )
    assert decision.gated is True
    assert decision.reason == "deploy"


def test_forward_auth_paths():
    from gate import LOCAL_ALIVE_PATH, LOCAL_AUTH_PATH

    assert LOCAL_AUTH_PATH == "/_maintenance/auth"
    assert LOCAL_ALIVE_PATH == "/_maintenance/alive"


def test_gate_scheduled_from_status():
    decision = decide_gate(
        flag_active=False,
        status={
            "maintenance": {
                "active": True,
                "reason": "scheduled",
                "message": "Offline until evening",
            }
        },
        status_fetch_ok=True,
    )
    assert decision.gated is True
    assert decision.reason == "scheduled"
    html = render_maintenance_html(
        "<h1><!--TITLE-->x<!--/TITLE--></h1><p><!--MESSAGE-->y<!--/MESSAGE--></p><!--DETAIL-->",
        decision,
    )
    assert "Offline until evening" in html
    assert "Scheduled maintenance" in html


def test_gate_open_when_status_ok():
    decision = decide_gate(
        flag_active=False,
        status={"maintenance": {"active": False}},
        status_fetch_ok=True,
        upstream_reachable=True,
    )
    assert decision.gated is False


def test_gate_fail_closed_when_status_unreachable():
    decision = decide_gate(
        flag_active=False,
        status=None,
        status_fetch_ok=False,
    )
    assert decision.gated is True
    assert decision.reason == "status_unreachable"


def test_always_pass_health_and_site_status():
    assert should_always_pass("/health")
    assert should_always_pass("/api/v1/site-status")
    assert not should_always_pass("/api/v1/auth/login", "POST")
    assert not should_always_pass("/")


@pytest.mark.asyncio
async def test_set_announcement_and_pending_ack():
    from uuid import uuid4

    from app.services import maintenance as maint

    store: dict[str, dict] = {}
    acks: list = []

    class FakeSetting:
        def __init__(self, key, value):
            self.key = key
            self.value = value
            self.updated_at = None

    class FakeAck:
        def __init__(self, user_id, announcement_id):
            self.user_id = user_id
            self.announcement_id = announcement_id

    class FakeDB:
        def add(self, obj):
            if isinstance(obj, FakeSetting) or getattr(obj, "key", None):
                store[obj.key] = obj.value
            else:
                acks.append(obj)

        async def flush(self):
            return None

        async def get(self, model, key):
            if key not in store:
                return None
            return FakeSetting(key, store[key])

        async def scalar(self, _stmt):
            return None

    # Patch SiteSetting construction path via _set_setting using FakeSetting-compatible
    async def fake_get(db, key):
        if key not in store:
            return None
        return FakeSetting(key, store[key])

    async def fake_set(db, key, value):
        store[key] = value
        return FakeSetting(key, value)

    # Monkeypatch internals used by set/get
    import app.services.maintenance as m

    original_get = m._get_setting
    original_set = m._set_setting
    m._get_setting = fake_get
    m._set_setting = fake_set

    try:
        db = FakeDB()
        payload = await maint.set_announcement(
            db, enabled=True, title="Hello", body="Please read this"
        )
        assert payload["enabled"] is True
        assert payload["id"]

        user_id = uuid4()
        pending = await maint.get_pending_announcement_for_user(db, user_id)
        assert pending is not None
        assert pending["body"] == "Please read this"

        # Simulate ack exists
        async def scalar_acked(_stmt):
            return FakeAck(user_id, payload["id"])

        db.scalar = scalar_acked  # type: ignore[method-assign]
        pending2 = await maint.get_pending_announcement_for_user(db, user_id)
        assert pending2 is None
    finally:
        m._get_setting = original_get
        m._set_setting = original_set
