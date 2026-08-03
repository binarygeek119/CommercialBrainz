"""Tests for SMTP helpers and verification email send failure surfacing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import email as email_svc
from app.services import email_verification as ev


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_smtp_configured_false_when_host_blank(monkeypatch):
    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(smtp_host=""),
    )
    assert email_svc.smtp_configured() is False


def test_smtp_configured_true_when_host_set(monkeypatch):
    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(smtp_host="smtp.example.com"),
    )
    assert email_svc.smtp_configured() is True


@pytest.mark.asyncio
async def test_send_email_skips_without_host(monkeypatch):
    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(
            smtp_host="",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            smtp_from="noreply@example.com",
        ),
    )
    assert await email_svc.send_email("a@b.c", "subj", "body") is False


@pytest.mark.asyncio
async def test_resend_raises_when_smtp_unavailable(monkeypatch):
    user = SimpleNamespace(id=uuid4(), email_verified=False, email="a@b.c", username="u")
    monkeypatch.setattr(ev, "send_verification_email_for_user", AsyncMock(return_value=False))
    monkeypatch.setattr(ev, "smtp_configured", lambda: False)
    with pytest.raises(RuntimeError, match="not configured"):
        await ev.resend_verification_email(AsyncMock(), user)


@pytest.mark.asyncio
async def test_resend_raises_when_send_fails(monkeypatch):
    user = SimpleNamespace(id=uuid4(), email_verified=False, email="a@b.c", username="u")
    monkeypatch.setattr(ev, "send_verification_email_for_user", AsyncMock(return_value=False))
    monkeypatch.setattr(ev, "smtp_configured", lambda: True)
    with pytest.raises(RuntimeError, match="Could not send"):
        await ev.resend_verification_email(AsyncMock(), user)


@pytest.mark.asyncio
async def test_health_includes_email_configured(client):
    with patch("app.services.email.smtp_configured", return_value=False):
        response = await client.get("/health")
    body = response.json()
    assert "email_configured" in body
    assert body["email_configured"] is False
