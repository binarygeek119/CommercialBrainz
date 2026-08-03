"""Outbound email via SMTP (verification, password reset, DMCA)."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when an email cannot be delivered via SMTP."""

    def __init__(self, public_message: str, *, detail: str | None = None):
        self.public_message = public_message
        self.detail = detail or public_message
        super().__init__(public_message)


def _strip_secret(value: str) -> str:
    """Normalize .env values that may be wrapped in quotes or padded."""
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return text


def smtp_configured() -> bool:
    """True when SMTP_HOST is set (outbound email can be attempted)."""
    return bool(_strip_secret(get_settings().smtp_host))


def smtp_credential_status() -> dict[str, Any]:
    """Non-secret SMTP readiness flags for health / admin UI."""
    settings = get_settings()
    host = _strip_secret(settings.smtp_host)
    user = _strip_secret(settings.smtp_user)
    password = _strip_secret(settings.smtp_password)
    from_addr = _strip_secret(settings.smtp_from)
    return {
        "configured": bool(host),
        "host_set": bool(host),
        "user_set": bool(user),
        "password_set": bool(password),
        "from_set": bool(from_addr),
        "port": settings.smtp_port,
        "use_ssl": bool(settings.smtp_use_ssl),
    }


def _public_smtp_error(exc: BaseException) -> str:
    """Map SMTP failures to actionable messages (no secrets)."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "SMTP authentication failed. Check SMTP_USER / SMTP_PASSWORD "
            "(Outlook often needs an app password, and Authenticated SMTP enabled)."
        )
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return (
            "The mail server rejected SMTP_FROM. Use the same address as SMTP_USER "
            "(or an alias allowed for that mailbox)."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "The mail server rejected the recipient address."
    if isinstance(exc, smtplib.SMTPConnectError):
        return f"Could not connect to SMTP_HOST:{get_settings().smtp_port}."
    if isinstance(exc, TimeoutError):
        return "Timed out connecting to the mail server."
    if isinstance(exc, ssl.SSLError):
        return "TLS/SSL handshake with the mail server failed."
    if isinstance(exc, OSError):
        return f"Network error reaching the mail server: {exc.__class__.__name__}."
    if isinstance(exc, smtplib.SMTPException):
        text = str(exc).strip() or exc.__class__.__name__
        # Keep short; avoid dumping full SMTP transcripts with credentials.
        return f"Mail server error: {text[:180]}"
    return f"Could not send email ({exc.__class__.__name__})."


def _send_email_sync(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    host = _strip_secret(settings.smtp_host)
    if not host:
        raise EmailSendError(
            "Email delivery is not configured on this server. "
            "Set SMTP_HOST (and credentials) in the app .env, then restart the API."
        )

    user = _strip_secret(settings.smtp_user)
    password = _strip_secret(settings.smtp_password)
    from_addr = _strip_secret(settings.smtp_from) or user
    if not from_addr:
        raise EmailSendError("SMTP_FROM (or SMTP_USER) must be set to send mail.")

    if user and not password:
        raise EmailSendError(
            "SMTP_USER is set but SMTP_PASSWORD is empty. "
            "Add the mailbox password or app password and restart the API."
        )

    msg = EmailMessage()
    msg["From"] = formataddr(("CommercialBrainz", from_addr))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1])
    msg.set_content(body)

    timeout = max(5, int(settings.smtp_timeout_sec))
    context = ssl.create_default_context()

    try:
        if settings.smtp_use_ssl or settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                host, settings.smtp_port, timeout=timeout, context=context
            ) as server:
                server.ehlo()
                if user:
                    server.login(user, password)
                server.send_message(msg, from_addr=from_addr, to_addrs=[to])
        else:
            with smtplib.SMTP(host, settings.smtp_port, timeout=timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                if user:
                    server.login(user, password)
                server.send_message(msg, from_addr=from_addr, to_addrs=[to])
    except EmailSendError:
        raise
    except Exception as exc:
        public = _public_smtp_error(exc)
        logger.exception(
            "Failed to send email to %s via %s:%s", to, host, settings.smtp_port
        )
        raise EmailSendError(public, detail=str(exc)) from exc


async def send_email(to: str, subject: str, body: str) -> bool:
    """
    Send email if SMTP is configured.

    Returns True on success. Raises EmailSendError on failure when SMTP is configured
    (or when required credentials are missing). Returns False only when SMTP_HOST is unset.
    """
    if not smtp_configured():
        logger.info(
            "SMTP not configured; skipping email to %s: %s",
            to,
            subject,
        )
        return False
    await asyncio.to_thread(_send_email_sync, to, subject, body)
    return True


async def notify_dmca_submitted(claimant_email: str, video_id: str) -> None:
    settings = get_settings()
    try:
        await send_email(
            claimant_email,
            "CommercialBrainz DMCA Notice Received",
            f"Your DMCA takedown request for video {video_id} "
            "has been received and is under review.",
        )
    except EmailSendError:
        logger.warning("DMCA claimant notification email failed for %s", claimant_email)
    try:
        await send_email(
            settings.dmca_contact,
            f"New DMCA submission for video {video_id}",
            f"A new DMCA takedown was submitted for video {video_id}. Review in the mod queue.",
        )
    except EmailSendError:
        logger.warning("DMCA staff notification email failed")


async def notify_dmca_decision(
    claimant_email: str,
    video_id: str,
    status: str,
) -> None:
    try:
        await send_email(
            claimant_email,
            f"CommercialBrainz DMCA Decision: {status}",
            f"Your DMCA request for video {video_id} has been updated to status: {status}.",
        )
    except EmailSendError:
        logger.warning("DMCA decision email failed for %s", claimant_email)


async def send_password_reset_email(
    to: str,
    username: str,
    reset_url: str,
) -> bool:
    settings = get_settings()
    minutes = settings.password_reset_expire_minutes
    body = (
        f"Hello {username},\n\n"
        "We received a request to reset your CommercialBrainz password.\n\n"
        f"Reset your password (link expires in {minutes} minutes):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "— CommercialBrainz"
    )
    try:
        return await send_email(to, "Reset your CommercialBrainz password", body)
    except EmailSendError:
        logger.warning("Password reset email failed for %s", to)
        return False


async def send_verification_email(
    to: str,
    username: str,
    verify_url: str,
) -> bool:
    settings = get_settings()
    hours = settings.email_verification_expire_minutes // 60
    if hours:
        expiry = f"{hours} hours"
    else:
        expiry = f"{settings.email_verification_expire_minutes} minutes"
    body = (
        f"Hello {username},\n\n"
        "Welcome to CommercialBrainz! Please verify your email address "
        "to vote and submit edits.\n\n"
        f"Verify your email (link expires in {expiry}):\n{verify_url}\n\n"
        "If you did not create this account, you can ignore this email.\n\n"
        "— CommercialBrainz"
    )
    return await send_email(to, "Verify your CommercialBrainz email", body)


async def send_admin_test_email(to: str) -> None:
    """Send a short connectivity probe used by the admin Email panel."""
    body = (
        "This is a CommercialBrainz SMTP test message.\n\n"
        "If you received this, outbound verification / reset mail should work.\n\n"
        "— CommercialBrainz"
    )
    sent = await send_email(to, "CommercialBrainz SMTP test", body)
    if not sent:
        raise EmailSendError(
            "Email delivery is not configured on this server. "
            "Set SMTP_HOST (and credentials) in the app .env, then restart the API."
        )
