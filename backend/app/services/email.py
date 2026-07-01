import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email if SMTP is configured. Returns True on success."""
    if not settings.smtp_host:
        logger.info("SMTP not configured; skipping email to %s: %s", to, subject)
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


async def notify_dmca_decision(claimant_email: str, video_id: str, status: str) -> None:
    await send_email(
        claimant_email,
        f"CommercialBrainz DMCA Decision: {status}",
        f"Your DMCA request for video {video_id} has been updated to status: {status}.",
    )
