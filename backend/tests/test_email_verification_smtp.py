"""Tests for SMTP helpers and verification email send failure surfacing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import email as email_svc
from app.services import email_verification as ev
from app.services.email import EmailSendError


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


def test_normalize_env_removes_quotes():
    assert email_svc._normalize_env('  "secret"  ') == "secret"
    assert email_svc._normalize_env("'secret'") == "secret"
    assert email_svc._normalize_smtp_password("abcd efgh ijkl mnop") == "abcdefghijklmnop"
    assert email_svc._log_safe("a\nb\rc") == "a b c"


def test_public_smtp_error_auth():
    import smtplib

    msg = email_svc._public_smtp_error(smtplib.SMTPAuthenticationError(535, b"fail"))
    assert "authentication failed" in msg.lower()


def test_public_smtp_error_microsoft_basic_auth_disabled(monkeypatch):
    import smtplib

    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(smtp_host="smtp-mail.outlook.com", smtp_port=587),
    )
    msg = email_svc._public_smtp_error(
        smtplib.SMTPAuthenticationError(
            535,
            b"5.7.139 Authentication unsuccessful, basic authentication is disabled",
        )
    )
    assert "basic auth is disabled" in msg.lower()
    assert "resend" in msg.lower()


def test_public_smtp_error_outlook_host_generic_auth(monkeypatch):
    import smtplib

    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(smtp_host="smtp.office365.com", smtp_port=587),
    )
    msg = email_svc._public_smtp_error(smtplib.SMTPAuthenticationError(535, b"auth fail"))
    assert "microsoft" in msg.lower()
    assert "app-password" in msg.lower() or "app password" in msg.lower()


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
            smtp_use_ssl=False,
            smtp_timeout_sec=30,
        ),
    )
    assert await email_svc.send_email("a@b.c", "subj", "body") is False


@pytest.mark.asyncio
async def test_send_email_raises_when_password_missing(monkeypatch):
    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="",
            smtp_from="user@example.com",
            smtp_use_ssl=False,
            smtp_timeout_sec=30,
        ),
    )
    with pytest.raises(EmailSendError, match="SMTP_PASSWORD"):
        await email_svc.send_email("a@b.c", "subj", "body")


@pytest.mark.asyncio
async def test_resend_raises_email_send_error(monkeypatch):
    user = SimpleNamespace(id=uuid4(), email_verified=False, email="a@b.c", username="u")
    monkeypatch.setattr(
        ev,
        "send_verification_email_for_user",
        AsyncMock(side_effect=EmailSendError("SMTP authentication failed.")),
    )
    with pytest.raises(EmailSendError, match="authentication failed"):
        await ev.resend_verification_email(AsyncMock(), user)


@pytest.mark.asyncio
async def test_resend_raises_when_smtp_unset(monkeypatch):
    user = SimpleNamespace(id=uuid4(), email_verified=False, email="a@b.c", username="u")
    monkeypatch.setattr(ev, "send_verification_email_for_user", AsyncMock(return_value=False))
    with pytest.raises(EmailSendError, match="not configured"):
        await ev.resend_verification_email(AsyncMock(), user)


def test_smtp_credential_status(monkeypatch):
    monkeypatch.setattr(
        email_svc,
        "get_settings",
        lambda: SimpleNamespace(
            smtp_host="smtp.office365.com",
            smtp_port=587,
            smtp_user="a@b.c",
            smtp_password="x",
            smtp_from="a@b.c",
            smtp_use_ssl=False,
        ),
    )
    status = email_svc.smtp_credential_status()
    assert status["configured"] is True
    assert status["user_set"] is True
    assert status["password_set"] is True
