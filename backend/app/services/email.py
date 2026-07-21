import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email if SMTP is configured. Returns True on success."""
    if not settings.smtp_host:
        logger.info(
    "SMTP not configured; skipping email to %s: %s",
    to,
     subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


async def notify_dmca_submitted(claimant_email: str, video_id: str) -> None:
    await send_email(
        claimant_email,
        "CommercialBrainz DMCA Notice Received",
        f"Your DMCA takedown request for video {video_id} has been received and is under review.",
    )
    await send_email(
        settings.dmca_contact,
        f"New DMCA submission for video {video_id}",
        f"A new DMCA takedown was submitted for video {video_id}. Review in the mod queue.",
    )


async def notify_dmca_decision(
    claimant_email: str,
    video_id: str,
     status: str) -> None:
    await send_email(
        claimant_email,
        f"CommercialBrainz DMCA Decision: {status}",
        f"Your DMCA request for video {video_id} has been updated to status: {status}.",
    )


async def send_password_reset_email(
    to: str,
    username: str,
     reset_url: str) -> bool:
    minutes = settings.password_reset_expire_minutes
    body = (
        f"Hello {username},\n\n"
        "We received a request to reset your CommercialBrainz password.\n\n"
        f"Reset your password (link expires in {minutes} minutes):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "— CommercialBrainz"
    )
    return await send_email(to, "Reset your CommercialBrainz password", body)


async def send_verification_email(
    to: str,
    username: str,
    verify_url: str,
) -> bool:
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
