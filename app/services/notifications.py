"""Multi-channel notification service: Slack, Email (Resend), SMS (Twilio)."""

import logging
from datetime import datetime

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level senders
# ---------------------------------------------------------------------------

async def send_slack_notification(webhook_url: str, message: str) -> bool:
    """POST a message to a Slack incoming webhook. Returns True on success."""
    if not webhook_url:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"text": message})
            if resp.status_code == 200:
                return True
            logger.warning("Slack webhook returned %s: %s", resp.status_code, resp.text)
            return False
    except Exception:
        logger.exception("Failed to send Slack notification")
        return False


async def send_email_notification(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via the Resend API. Returns True on success."""
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured; skipping email to %s", to_email)
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Resend API returned %s: %s", resp.status_code, resp.text)
            return False
    except Exception:
        logger.exception("Failed to send email via Resend to %s", to_email)
        return False


async def send_sms(to_phone: str, body: str) -> bool:
    """Send an SMS via the Twilio REST API. Returns True on success."""
    settings = get_settings()
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured; skipping SMS to %s", to_phone)
        return False

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={
                    "From": settings.TWILIO_PHONE_NUMBER,
                    "To": to_phone,
                    "Body": body,
                },
            )
            if resp.status_code in (200, 201):
                return True
            logger.warning("Twilio API returned %s: %s", resp.status_code, resp.text)
            return False
    except Exception:
        logger.exception("Failed to send SMS via Twilio to %s", to_phone)
        return False


# ---------------------------------------------------------------------------
# High-level notification helpers
# ---------------------------------------------------------------------------

async def notify_team_new_booking(business, lead, appointment, db=None) -> None:
    """Notify the business team about a new appointment booking via all
    configured channels (Slack, email, SMS).
    """
    lead_name = lead.name or "Unknown"
    lead_phone = lead.phone or "N/A"
    lead_email = lead.email or "N/A"
    service = appointment.service_name or "General"
    scheduled = appointment.scheduled_at
    scheduled_str = (
        scheduled.strftime("%A, %B %d at %-I:%M %p")
        if isinstance(scheduled, datetime)
        else str(scheduled)
    )

    text_msg = (
        f"New Appointment Booked!\n"
        f"Customer: {lead_name}\n"
        f"Phone: {lead_phone}\n"
        f"Email: {lead_email}\n"
        f"Service: {service}\n"
        f"Scheduled: {scheduled_str}\n"
    )

    html_msg = (
        f"<h3>New Appointment Booked</h3>"
        f"<p><strong>Customer:</strong> {lead_name}<br>"
        f"<strong>Phone:</strong> {lead_phone}<br>"
        f"<strong>Email:</strong> {lead_email}<br>"
        f"<strong>Service:</strong> {service}<br>"
        f"<strong>Scheduled:</strong> {scheduled_str}</p>"
    )

    # Slack
    if business.slack_webhook_url:
        await send_slack_notification(business.slack_webhook_url, text_msg)

    # Email to all notification emails
    if business.notification_emails:
        for email_addr in business.notification_emails:
            await send_email_notification(
                email_addr,
                f"New Booking: {lead_name} - {service}",
                html_msg,
            )

    # SMS to notification phone
    if business.notification_phone:
        await send_sms(business.notification_phone, text_msg)


async def notify_team_new_lead(business, lead) -> None:
    """Send a lighter notification when a new qualified lead is captured."""
    lead_name = lead.name or "Unknown"
    lead_phone = lead.phone or "N/A"
    pain_point = lead.pain_point or "Not specified"

    text_msg = (
        f"New Lead Captured!\n"
        f"Name: {lead_name}\n"
        f"Phone: {lead_phone}\n"
        f"Need: {pain_point}\n"
        f"Score: {lead.score or 0}/100"
    )

    if business.slack_webhook_url:
        await send_slack_notification(business.slack_webhook_url, text_msg)

    if business.notification_emails:
        html_msg = (
            f"<h3>New Lead Captured</h3>"
            f"<p><strong>Name:</strong> {lead_name}<br>"
            f"<strong>Phone:</strong> {lead_phone}<br>"
            f"<strong>Need:</strong> {pain_point}<br>"
            f"<strong>Score:</strong> {lead.score or 0}/100</p>"
        )
        for email_addr in business.notification_emails:
            await send_email_notification(
                email_addr,
                f"New Lead: {lead_name}",
                html_msg,
            )


async def send_appointment_reminder(
    lead,
    appointment,
    business,
    reminder_type: str,
) -> bool:
    """Send a 24-hour or 1-hour appointment reminder to the lead.

    ``reminder_type`` should be ``"24h"`` or ``"1h"``.
    Returns True if at least one notification was sent successfully.
    """
    lead_name = lead.name or "there"
    service = appointment.service_name or "your appointment"
    scheduled = appointment.scheduled_at
    scheduled_str = (
        scheduled.strftime("%A, %B %d at %-I:%M %p")
        if isinstance(scheduled, datetime)
        else str(scheduled)
    )
    business_name = business.name

    if reminder_type == "24h":
        subject = f"Reminder: Your appointment tomorrow with {business_name}"
        body = (
            f"Hi {lead_name}, this is a reminder that you have "
            f"{service} scheduled for {scheduled_str} with {business_name}. "
            f"We look forward to seeing you!"
        )
    else:
        subject = f"Reminder: Your appointment in 1 hour with {business_name}"
        body = (
            f"Hi {lead_name}, just a quick reminder that your "
            f"{service} appointment with {business_name} is coming up "
            f"at {scheduled_str}. See you soon!"
        )

    sent = False

    # SMS
    if lead.phone:
        sms_ok = await send_sms(lead.phone, body)
        sent = sent or sms_ok

    # Email
    if lead.email:
        html_body = f"<p>{body}</p>"
        email_ok = await send_email_notification(lead.email, subject, html_body)
        sent = sent or email_ok

    return sent
