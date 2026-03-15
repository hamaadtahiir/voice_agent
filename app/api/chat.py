"""WebSocket chat endpoint for web widget."""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.engine import async_session_factory
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.services.channel_router import Channel, NormalizedMessage, route_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/chat/{business_slug}")
async def websocket_chat(websocket: WebSocket, business_slug: str):
    """Handle real-time chat via WebSocket for a specific business."""
    await websocket.accept()

    async with async_session_factory() as db:
        # Look up business by slug
        result = await db.execute(
            select(Business).where(
                Business.slug == business_slug,
                Business.is_active == True,  # noqa: E712
            )
        )
        business = result.scalar_one_or_none()
        if not business:
            await websocket.send_json({"type": "error", "content": "Business not found"})
            await websocket.close(code=4004)
            return

        # Generate a session ID for this websocket connection
        session_id = str(uuid.uuid4())

        # Send welcome message
        welcome = "Hi! How can we help you today?"
        if business.branding and isinstance(business.branding, dict):
            welcome = business.branding.get("welcome_message", welcome)

        await websocket.send_json({
            "type": "message",
            "content": welcome,
            "session_id": session_id,
        })

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"content": raw}

                content = data.get("content", "").strip()
                if not content:
                    continue

                # Route through conversation engine
                normalized = NormalizedMessage(
                    channel=Channel.WEB_CHAT,
                    sender_id=session_id,
                    content=content,
                    metadata=data.get("metadata"),
                )

                try:
                    response = await route_message(normalized, business, db)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception("Error processing chat message")
                    await websocket.send_json({
                        "type": "error",
                        "content": "Sorry, something went wrong. Please try again.",
                    })
                    continue

                await websocket.send_json({
                    "type": "message",
                    "content": response,
                })

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected: session=%s", session_id)
        except Exception:
            logger.exception("Unexpected WebSocket error: session=%s", session_id)
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": "Sorry, something went wrong. Please try again.",
                })
            except Exception:
                pass
