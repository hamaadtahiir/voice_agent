"""Multi-channel adapter pattern for normalising inbound messages and
routing responses back through the correct channel.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class Channel(str, Enum):
    WEB_CHAT = "web_chat"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    EMAIL = "email"
    SMS = "sms"


@dataclass
class NormalizedMessage:
    channel: Channel
    sender_id: str  # external identifier (phone number, session id, etc.)
    content: str
    media_urls: list[str] | None = None
    metadata: dict | None = None


@dataclass
class OutboundMessage:
    content: str
    media_urls: list[str] | None = None


# ---------------------------------------------------------------------------
# Channel adapters
# ---------------------------------------------------------------------------

class ChannelAdapter:
    """Base adapter class."""

    async def send_message(self, recipient_id: str, message: OutboundMessage) -> bool:
        raise NotImplementedError


class WhatsAppAdapter(ChannelAdapter):
    """Send messages via the WhatsApp Cloud API."""

    def __init__(self, phone_number_id: str, access_token: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token

    async def send_message(self, recipient_id: str, message: OutboundMessage) -> bool:
        url = (
            f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        )
        payload: dict = {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "text",
            "text": {"body": message.content},
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    return True
                logger.warning("WhatsApp API returned %s: %s", resp.status_code, resp.text)
                return False
        except Exception:
            logger.exception("Failed to send WhatsApp message to %s", recipient_id)
            return False


class SMSAdapter(ChannelAdapter):
    """Send messages via Twilio."""

    async def send_message(self, recipient_id: str, message: OutboundMessage) -> bool:
        from app.services.notifications import send_sms
        return await send_sms(recipient_id, message.content)


class EmailAdapter(ChannelAdapter):
    """Send messages via Resend."""

    def __init__(self, from_email: str | None = None):
        self.from_email = from_email

    async def send_message(self, recipient_id: str, message: OutboundMessage) -> bool:
        from app.services.notifications import send_email_notification
        html = f"<p>{message.content}</p>"
        return await send_email_notification(recipient_id, "New message", html)


class WebChatAdapter(ChannelAdapter):
    """Web chat messages are returned directly via the API response; this
    adapter is a no-op stub for symmetry."""

    async def send_message(self, recipient_id: str, message: OutboundMessage) -> bool:
        # Web chat responses are returned inline via the HTTP response.
        return True


def get_adapter(channel: Channel, business=None) -> ChannelAdapter:
    """Return the appropriate adapter for the given channel."""
    settings = get_settings()

    if channel == Channel.WHATSAPP and business:
        return WhatsAppAdapter(
            phone_number_id=business.whatsapp_phone_number_id or "",
            access_token=business.whatsapp_access_token or "",
        )
    if channel == Channel.SMS:
        return SMSAdapter()
    if channel == Channel.EMAIL:
        return EmailAdapter(from_email=settings.RESEND_FROM_EMAIL)
    return WebChatAdapter()


# ---------------------------------------------------------------------------
# Core routing
# ---------------------------------------------------------------------------

async def _find_or_create_lead(
    business_id: uuid.UUID,
    sender_id: str,
    channel: Channel,
    db: AsyncSession,
) -> Lead:
    """Look up an existing lead by (business_id, external_id, channel) or
    create a new one.
    """
    result = await db.execute(
        select(Lead).where(
            Lead.business_id == business_id,
            Lead.external_id == sender_id,
            Lead.channel == channel.value,
        )
    )
    lead = result.scalar_one_or_none()
    if lead:
        return lead

    lead = Lead(
        business_id=business_id,
        external_id=sender_id,
        channel=channel.value,
        status="new",
    )
    db.add(lead)
    await db.flush()
    return lead


async def _find_or_create_conversation(
    lead: Lead,
    business_id: uuid.UUID,
    channel: Channel,
    db: AsyncSession,
) -> Conversation:
    """Find the active conversation for a lead, or create a new one."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.lead_id == lead.id,
            Conversation.business_id == business_id,
            Conversation.is_active == True,  # noqa: E712
        )
    )
    convo = result.scalar_one_or_none()
    if convo:
        return convo

    convo = Conversation(
        lead_id=lead.id,
        business_id=business_id,
        channel=channel.value,
        current_node="greeting",
        is_active=True,
    )
    db.add(convo)
    await db.flush()
    return convo


def _build_initial_state(business: Business, lead: Lead, conversation: Conversation) -> dict:
    """Build the initial LangGraph ConversationState dict from DB objects."""
    branding = business.branding or {}
    services = business.services or []
    service_areas = business.service_areas or []

    welcome = branding.get("welcome_message") or (
        f"Welcome to {business.name}! How can we help you today?"
    )
    system_prompt = business.system_prompt_override or (
        f"You are a friendly and professional AI assistant for {business.name}, "
        f"a {business.industry} business. Help qualify leads and schedule appointments."
    )

    return {
        "messages": [],
        "business_id": str(business.id),
        "business_name": business.name,
        "business_industry": business.industry or "",
        "business_timezone": business.timezone or "America/New_York",
        "business_services": services,
        "business_service_areas": service_areas,
        "business_hours": business.business_hours or {},
        "welcome_message": welcome,
        "system_prompt": system_prompt,
        "channel": lead.channel,
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "lead_email": lead.email,
        "lead_location_zip": lead.location_zip,
        "lead_location_city": lead.location_city,
        "lead_location_state": lead.location_state,
        "in_service_area": None,
        "pain_point": lead.pain_point,
        "identified_service": lead.identified_service,
        "available_slots": None,
        "selected_slot": None,
        "appointment_id": None,
        "quote_range": None,
        "current_node": conversation.current_node or "greeting",
        "needs_media": False,
        "media_urls": list(lead.media_urls or []),
        "conversation_id": str(conversation.id),
    }


async def route_message(
    message: NormalizedMessage,
    business: Business,
    db: AsyncSession,
) -> str:
    """Main entry point: normalise an inbound message, find or create the lead
    and conversation, invoke the LangGraph flow, persist messages, and return
    the assistant's response text.
    """
    # 1. Find or create lead
    lead = await _find_or_create_lead(
        business.id, message.sender_id, message.channel, db
    )

    # 2. Find or create active conversation
    conversation = await _find_or_create_conversation(
        lead, business.id, message.channel, db
    )

    # 3. Save the incoming message
    incoming_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=message.content,
        media_url=message.media_urls[0] if message.media_urls else None,
        metadata_=message.metadata,
    )
    db.add(incoming_msg)
    await db.flush()

    # 4. Restore or build graph state
    if conversation.graph_state:
        state = conversation.graph_state
        # Ensure mutable fields exist
        state.setdefault("messages", [])
    else:
        state = _build_initial_state(business, lead, conversation)

    # 5. Import and invoke LangGraph flow (runtime import to avoid circular deps)
    from app.graph.flow import run_graph

    updated_state = await run_graph(state, user_message=message.content)

    # 6. Extract the assistant response (last AI message)
    response_text = ""
    for msg in reversed(updated_state.get("messages", [])):
        # Support both dict and LangChain message objects
        if hasattr(msg, "type"):
            if msg.type == "ai":
                response_text = msg.content
                break
        elif isinstance(msg, dict) and msg.get("role") == "assistant":
            response_text = msg.get("content", "")
            break

    if not response_text:
        response_text = "Thank you for reaching out! How can I help you today?"

    # 7. Save assistant response message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
    )
    db.add(assistant_msg)

    # 8. Update conversation state in DB
    # Serialise LangChain messages to dicts for JSON storage
    serialised_messages = []
    for msg in updated_state.get("messages", []):
        if hasattr(msg, "model_dump"):
            serialised_messages.append(msg.model_dump())
        elif hasattr(msg, "dict"):
            serialised_messages.append(msg.dict())
        elif isinstance(msg, dict):
            serialised_messages.append(msg)
    state_to_save = dict(updated_state)
    state_to_save["messages"] = serialised_messages
    conversation.graph_state = state_to_save
    conversation.current_node = updated_state.get("current_node", conversation.current_node)

    # 9. Update lead
    lead.last_message_at = datetime.now(timezone.utc)
    if lead.status == "new":
        lead.status = "qualifying"

    # Sync lead fields from state
    if updated_state.get("lead_name") and not lead.name:
        lead.name = updated_state["lead_name"]
    if updated_state.get("lead_phone") and not lead.phone:
        lead.phone = updated_state["lead_phone"]
    if updated_state.get("lead_email") and not lead.email:
        lead.email = updated_state["lead_email"]
    if updated_state.get("lead_location_zip") and not lead.location_zip:
        lead.location_zip = updated_state["lead_location_zip"]
    if updated_state.get("lead_location_city") and not lead.location_city:
        lead.location_city = updated_state["lead_location_city"]
    if updated_state.get("lead_location_state") and not lead.location_state:
        lead.location_state = updated_state["lead_location_state"]
    if updated_state.get("pain_point") and not lead.pain_point:
        lead.pain_point = updated_state["pain_point"]
    if updated_state.get("identified_service") and not lead.identified_service:
        lead.identified_service = updated_state["identified_service"]
    if updated_state.get("in_service_area") is not None:
        lead.location_zip = updated_state.get("lead_location_zip") or lead.location_zip

    await db.flush()

    return response_text
