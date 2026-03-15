"""Inbound email webhook route."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.business import Business
from app.services.channel_router import Channel, NormalizedMessage, route_message
from app.services.notifications import send_email_notification

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/email")
async def receive_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive inbound email from a webhook provider (e.g. Resend, SendGrid).

    Expected JSON payload fields:
    - from / from_email: sender email address
    - from_name: sender display name (optional)
    - to / to_email: recipient email address
    - subject: email subject
    - text / body / plain: plain text body
    - html: HTML body (optional)
    """
    body: dict[str, Any] = await request.json()

    sender_email = (
        body.get("from")
        or body.get("from_email")
        or body.get("sender", "")
    )
    sender_name = body.get("from_name", "")
    to_email = body.get("to") or body.get("to_email") or body.get("recipient", "")
    subject = body.get("subject", "")
    text_body = (
        body.get("text")
        or body.get("body")
        or body.get("plain")
        or body.get("stripped-text")
        or ""
    )
    html_body = body.get("html", "")

    if not sender_email:
        logger.warning("Inbound email missing sender address")
        return {"status": "ignored", "reason": "no sender"}

    # Use the text body, falling back to a note about HTML-only content
    content = text_body.strip()
    if not content and html_body:
        content = "[HTML email - see original for full content]"
    if not content:
        content = subject or "[Empty email]"

    # Prepend subject if available and not already the content
    if subject and content != subject:
        content = f"Subject: {subject}\n\n{content}"

    # Try to find the business by matching the "to" email
    business = None
    if to_email:
        # Normalize: extract email from "Name <email>" format
        clean_to = to_email
        if "<" in clean_to and ">" in clean_to:
            clean_to = clean_to.split("<")[1].split(">")[0]
        clean_to = clean_to.strip().lower()

        result = await db.execute(
            select(Business).where(
                Business.email == clean_to,
                Business.is_active == True,  # noqa: E712
            )
        )
        business = result.scalar_one_or_none()

    # If no match on email, try the first active business as a fallback
    if not business:
        result = await db.execute(
            select(Business)
            .where(Business.is_active == True)  # noqa: E712
            .order_by(Business.created_at.asc())
            .limit(1)
        )
        business = result.scalar_one_or_none()

    if not business:
        logger.warning("No active business found for inbound email to=%s", to_email)
        return {"status": "ignored", "reason": "no matching business"}

    # Normalize sender email for consistent identification
    clean_sender = sender_email
    if "<" in clean_sender and ">" in clean_sender:
        clean_sender = clean_sender.split("<")[1].split(">")[0]
    clean_sender = clean_sender.strip().lower()

    # Route through conversation engine
    normalized = NormalizedMessage(
        channel=Channel.EMAIL,
        sender_id=clean_sender,
        content=content,
        metadata={
            "sender_name": sender_name,
            "sender_email": clean_sender,
            "to_email": to_email,
            "subject": subject,
            "has_html": bool(html_body),
        },
    )

    try:
        response_text = await route_message(normalized, business, db)
    except Exception:
        logger.exception("Error processing inbound email from %s", clean_sender)
        return {"status": "error", "reason": "processing failed"}

    # Send reply email
    try:
        reply_subject = f"Re: {subject}" if subject else "We received your message"
        reply_html = f"<p>{response_text}</p>"
        await send_email_notification(
            to_email=clean_sender,
            subject=reply_subject,
            html_body=reply_html,
        )
    except Exception:
        logger.exception("Failed to send email reply to %s", clean_sender)

    return {"status": "ok"}
