"""WhatsApp webhook routes."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.business import Business
from app.services.channel_router import Channel, NormalizedMessage, route_message
from app.services.encryption import decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhooks/whatsapp")
async def whatsapp_verify(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Verify the WhatsApp webhook subscription."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhooks/whatsapp")
async def whatsapp_receive(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process incoming WhatsApp messages."""
    body: dict[str, Any] = await request.json()

    # WhatsApp Cloud API sends a standard envelope
    entries = body.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})

            # Ignore non-message events (status updates, etc.)
            messages = value.get("messages")
            if not messages:
                continue

            # Extract phone number ID the message was sent to
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            if not phone_number_id:
                logger.warning("WhatsApp message missing phone_number_id")
                continue

            # Find the business associated with this phone number
            result = await db.execute(
                select(Business).where(
                    Business.whatsapp_phone_number_id == phone_number_id,
                    Business.is_active == True,  # noqa: E712
                )
            )
            business = result.scalar_one_or_none()
            if not business:
                logger.warning(
                    "No business found for WhatsApp phone_number_id=%s",
                    phone_number_id,
                )
                continue

            contacts = value.get("contacts", [])
            contact_name = None
            if contacts:
                profile = contacts[0].get("profile", {})
                contact_name = profile.get("name")

            for msg in messages:
                sender = msg.get("from", "")
                msg_type = msg.get("type", "text")
                timestamp = msg.get("timestamp")

                # Extract text content
                content = ""
                media_url = None

                if msg_type == "text":
                    content = msg.get("text", {}).get("body", "")
                elif msg_type in ("image", "video", "audio", "document"):
                    media_obj = msg.get(msg_type, {})
                    media_url = media_obj.get("id")  # media ID to be fetched
                    content = media_obj.get("caption", f"[{msg_type}]")
                elif msg_type == "location":
                    loc = msg.get("location", {})
                    content = f"Location: {loc.get('latitude')}, {loc.get('longitude')}"
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    itype = interactive.get("type", "")
                    if itype == "button_reply":
                        content = interactive.get("button_reply", {}).get("title", "")
                    elif itype == "list_reply":
                        content = interactive.get("list_reply", {}).get("title", "")
                    else:
                        content = str(interactive)
                else:
                    content = f"[{msg_type} message]"

                if not content.strip():
                    continue

                # Route through conversation engine
                normalized = NormalizedMessage(
                    channel=Channel.WHATSAPP,
                    sender_id=sender,
                    content=content,
                    metadata={
                        "contact_name": contact_name,
                        "message_type": msg_type,
                        "media_url": media_url,
                        "timestamp": timestamp,
                    },
                )

                try:
                    response_text = await route_message(normalized, business, db)
                except Exception:
                    logger.exception("Error processing WhatsApp message from %s", sender)
                    response_text = "Sorry, something went wrong. Please try again shortly."

                # Send reply via WhatsApp Cloud API
                try:
                    access_token = decrypt_value(business.whatsapp_access_token)
                except Exception:
                    access_token = business.whatsapp_access_token

                await _send_whatsapp_message(
                    phone_number_id=phone_number_id,
                    to=sender,
                    text=response_text,
                    access_token=access_token,
                )

    return {"status": "ok"}


async def _send_whatsapp_message(
    phone_number_id: str,
    to: str,
    text: str,
    access_token: str,
) -> None:
    """Send a text message via the WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error(
                "WhatsApp send failed: status=%s body=%s",
                resp.status_code,
                resp.text,
            )
