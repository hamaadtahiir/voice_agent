"""Vapi voice AI webhook routes."""

import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.services.calendar_service import get_available_slots, create_calendar_event
from app.services.lead_scoring import score_lead
from app.services.notifications import notify_team_new_booking

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_assistant_config(business: Business | None) -> dict:
    """Build the Vapi assistant configuration for a business."""
    settings = get_settings()
    server_url = f"{settings.BASE_URL}/webhooks/vapi" if settings.BASE_URL else None

    system_prompt = (
        "You are a friendly and professional AI assistant for a business. "
        "Your job is to qualify leads and help them book appointments. "
        "Ask for their name, what service they need, and their preferred time."
    )
    first_message = "Hello! Thank you for calling. How can I help you today?"

    if business:
        if business.system_prompt_override:
            system_prompt = business.system_prompt_override
        first_message = f"Hello! Thank you for calling {business.name}. How can I help you today?"

    # Vapi custom tools: each tool needs a server.url so Vapi sends
    # tool-calls to our webhook instead of trying to handle them internally.
    server_block = {"url": server_url} if server_url else {}

    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "Check available appointment slots for a given date",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date to check in YYYY-MM-DD format",
                        },
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service requested",
                        },
                    },
                    "required": ["date"],
                },
            },
            "server": server_block,
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book an appointment for the caller",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date in YYYY-MM-DD format",
                        },
                        "time": {
                            "type": "string",
                            "description": "Time in HH:MM format (24h)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Caller's name",
                        },
                        "phone": {
                            "type": "string",
                            "description": "Caller's phone number",
                        },
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service to book",
                        },
                    },
                    "required": ["date", "time", "name"],
                },
            },
            "server": server_block,
        },
    ]

    return {
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": system_prompt}],
            "tools": tools,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
        },
        "firstMessage": first_message,
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "serverUrl": server_url,
    }


async def sync_vapi_assistant(business: Business) -> bool:
    """Push assistant configuration to Vapi via their API.

    Call this after saving a business that has vapi_assistant_id set.
    Returns True on success, False on failure.
    """
    settings = get_settings()
    if not settings.VAPI_API_KEY or not business.vapi_assistant_id:
        logger.info("sync_vapi_assistant: skipped (no API key or assistant ID)")
        return False

    config = _build_assistant_config(business)

    # Also set the serverUrl so Vapi sends events to our webhook
    if settings.BASE_URL:
        config["serverUrl"] = f"{settings.BASE_URL}/webhooks/vapi"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"https://api.vapi.ai/assistant/{business.vapi_assistant_id}",
                json=config,
                headers={
                    "Authorization": f"Bearer {settings.VAPI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 200:
            logger.info("Synced Vapi assistant %s for business %s",
                        business.vapi_assistant_id, business.slug)
            return True
        else:
            logger.warning("Failed to sync Vapi assistant: %s %s",
                           resp.status_code, resp.text)
            return False
    except Exception:
        logger.exception("Error syncing Vapi assistant for business %s", business.slug)
        return False


@router.post("/webhooks/vapi")
async def vapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Vapi webhook events.

    Payload types:
    - assistant-request: return assistant configuration
    - function-call: execute tool calls (check_availability, book_appointment)
    - end-of-call-report: save lead/conversation record
    """
    body: dict = await request.json()
    # Vapi wraps all webhook payloads inside a "message" object
    message = body.get("message", body)
    payload_type = message.get("type", "")
    logger.info("Vapi webhook: type=%s, body_keys=%s, message_keys=%s",
                payload_type, list(body.keys()), list(message.keys()))

    if payload_type == "assistant-request":
        return await _handle_assistant_request(message, db)
    elif payload_type in ("function-call", "tool-calls"):
        return await _handle_tool_calls(message, db)
    elif payload_type == "end-of-call-report":
        return await _handle_end_of_call_report(message, db)
    else:
        logger.info("Unhandled Vapi payload type: %s", payload_type)
        return {"status": "ok"}


async def _handle_assistant_request(body: dict, db: AsyncSession) -> dict:
    """Return assistant configuration for an incoming call."""
    call_data = body.get("call", {})

    # Try to find the business by vapi_phone_number_id
    phone_number_id = call_data.get("phoneNumberId")
    logger.info("assistant-request: phoneNumberId=%s", phone_number_id)
    business = None
    if phone_number_id:
        result = await db.execute(
            select(Business).where(
                Business.vapi_phone_number_id == phone_number_id,
                Business.is_active == True,  # noqa: E712
            )
        )
        business = result.scalar_one_or_none()

    logger.info("assistant-request: business=%s", business.slug if business else "NOT FOUND")

    return {"assistant": _build_assistant_config(business)}


async def _handle_tool_calls(body: dict, db: AsyncSession) -> dict:
    """Execute tool calls requested by the Vapi assistant.

    Vapi sends tool calls in body["toolCallList"] with each item having:
      - id: tool call ID (must be returned in response)
      - name: function name
      - arguments: dict of parameters
    Response format: {"results": [{"toolCallId": "...", "result": "..."}]}
    """
    call_data = body.get("call", {})
    phone_number_id = call_data.get("phoneNumberId")

    # Look up business
    business = None
    if phone_number_id:
        result = await db.execute(
            select(Business).where(
                Business.vapi_phone_number_id == phone_number_id,
                Business.is_active == True,  # noqa: E712
            )
        )
        business = result.scalar_one_or_none()

    # Extract tool calls — try Vapi's current format first, fall back to legacy
    tool_call_list = body.get("toolCallList", [])

    # Fallback: toolWithToolCallList (alternative Vapi format where each item
    # contains both the tool definition and the call)
    if not tool_call_list:
        twtcl = body.get("toolWithToolCallList", [])
        for item in twtcl:
            tc = item.get("toolCall", {})
            function_obj = tc.get("function", {})
            tool_call_list.append({
                "id": tc.get("id", ""),
                "function": function_obj,
            })

    if not tool_call_list:
        # Legacy format fallback
        fc = body.get("functionCall", body.get("function_call", {}))
        if fc:
            tool_call_list = [{"id": "legacy", "function": {"name": fc.get("name", ""), "arguments": fc.get("parameters", {})}}]

    logger.info("tool-calls: %d calls, business=%s",
                len(tool_call_list), business.slug if business else "NOT FOUND")

    results = []
    for tc in tool_call_list:
        tool_call_id = tc.get("id", "")
        # Vapi nests name/arguments inside a "function" object (OpenAI format)
        function_obj = tc.get("function", {})
        fn_name = function_obj.get("name", "") or tc.get("name", "")
        raw_args = function_obj.get("arguments", "{}") or tc.get("arguments", "{}")
        # arguments can be a JSON string or already a dict
        if isinstance(raw_args, str):
            try:
                params = json.loads(raw_args)
            except (json.JSONDecodeError, TypeError):
                params = {}
        else:
            params = raw_args or {}
        logger.info("tool-call: id=%s fn=%s params=%s", tool_call_id, fn_name, params)

        if fn_name == "check_availability":
            result_str = await _fn_check_availability(params, business, db)
        elif fn_name == "book_appointment":
            result_str = await _fn_book_appointment(params, business, db)
        else:
            result_str = f"Unknown function: {fn_name}"

        results.append({"toolCallId": tool_call_id, "result": result_str})

    return {"results": results}


async def _fn_check_availability(
    params: dict, business: Business | None, db: AsyncSession
) -> str:
    """Check available appointment slots. Returns a string result."""
    date_str = params.get("date", "")
    service_name = params.get("service_name")

    if not business:
        return "I'm sorry, I couldn't identify the business. Please try again."

    try:
        duration = business.appointment_duration_default or 60
        slots = await get_available_slots(
            business=business,
            date_str=date_str,
            duration_minutes=duration,
        )
        if slots:
            slot_strings = [
                s.get("start", str(s)) if isinstance(s, dict) else str(s)
                for s in slots
            ]
            return f"Available times on {date_str}: {', '.join(slot_strings)}"
        else:
            return f"Sorry, there are no available slots on {date_str}. Would you like to try another date?"
    except Exception:
        logger.exception("Error checking availability")
        return "I had trouble checking availability. Could you please try a different date?"


async def _fn_book_appointment(
    params: dict, business: Business | None, db: AsyncSession
) -> str:
    """Book an appointment and create lead record. Returns a string result."""
    if not business:
        return "I'm sorry, I couldn't identify the business."

    name = params.get("name", "")
    phone = params.get("phone", "")
    date_str = params.get("date", "")
    time_str = params.get("time", "")
    service_name = params.get("service_name")

    try:
        scheduled_at = datetime.strptime(
            f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return "I couldn't parse that date and time. Please provide date as YYYY-MM-DD and time as HH:MM."

    # Create or find lead
    lead_result = await db.execute(
        select(Lead).where(
            Lead.business_id == business.id,
            Lead.phone == phone,
            Lead.channel == "phone",
        )
    )
    lead = lead_result.scalar_one_or_none()
    if not lead:
        lead = Lead(
            id=uuid.uuid4(),
            business_id=business.id,
            channel="phone",
            name=name,
            phone=phone,
            status="qualified",
            identified_service=service_name,
        )
        db.add(lead)
        await db.flush()

    # Create appointment
    from app.models.appointment import Appointment

    duration = business.appointment_duration_default or 60
    appointment = Appointment(
        id=uuid.uuid4(),
        business_id=business.id,
        lead_id=lead.id,
        scheduled_at=scheduled_at,
        duration_minutes=duration,
        service_name=service_name,
        status="scheduled",
    )
    db.add(appointment)

    # Update lead status
    lead.status = "appointment_booked"
    await db.flush()

    # Try to create calendar event
    try:
        event_result = await create_calendar_event(
            business=business,
            lead=lead,
            appointment_data={
                "scheduled_at": scheduled_at,
                "duration_minutes": duration,
                "service_name": service_name,
            },
        )
        if event_result:
            appointment.google_event_id = event_result.get("event_id")
            appointment.google_event_link = event_result.get("event_link")
            await db.flush()
    except Exception:
        logger.warning("Failed to create calendar event for appointment %s", appointment.id)

    # Notify team
    try:
        await notify_team_new_booking(business=business, lead=lead, appointment=appointment)
    except Exception:
        logger.warning("Failed to send booking notification for appointment %s", appointment.id)

    return (
        f"Great! I've booked your appointment for {date_str} at {time_str}. "
        f"We look forward to seeing you, {name}!"
    )


async def _handle_end_of_call_report(body: dict, db: AsyncSession) -> dict:
    """Process end-of-call report: create/update lead and conversation records."""
    call_data = body.get("call", {})

    phone_number_id = call_data.get("phoneNumberId")
    caller_number = call_data.get("customer", {}).get("number", "")
    call_id = call_data.get("id", str(uuid.uuid4()))

    # Transcript and summary
    transcript = body.get("transcript", "")
    summary = body.get("summary", "")
    ended_reason = body.get("endedReason", "")
    duration_seconds = body.get("duration") or call_data.get("duration")

    # Look up business
    business = None
    if phone_number_id:
        result = await db.execute(
            select(Business).where(
                Business.vapi_phone_number_id == phone_number_id,
                Business.is_active == True,  # noqa: E712
            )
        )
        business = result.scalar_one_or_none()

    if not business:
        logger.warning("No business found for Vapi phone_number_id=%s", phone_number_id)
        return {"status": "ok"}

    # Find or create lead
    lead = None
    if caller_number:
        lead_result = await db.execute(
            select(Lead).where(
                Lead.business_id == business.id,
                Lead.phone == caller_number,
                Lead.channel == "phone",
            )
        )
        lead = lead_result.scalar_one_or_none()

    if not lead:
        lead = Lead(
            id=uuid.uuid4(),
            business_id=business.id,
            channel="phone",
            phone=caller_number or None,
            external_id=call_id,
            status="qualifying",
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(lead)
        await db.flush()

    # Score the lead using the rule-based scorer
    try:
        lead_data = {
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "location_zip": lead.location_zip,
            "location_city": lead.location_city,
            "pain_point": lead.pain_point,
            "identified_service": lead.identified_service,
            "media_urls": lead.media_urls,
        }
        total_score, breakdown = score_lead(lead_data)
        lead.score = total_score
        lead.score_breakdown = breakdown
    except Exception:
        logger.exception("Error scoring lead %s", lead.id)

    # Create conversation record
    conversation = Conversation(
        id=uuid.uuid4(),
        lead_id=lead.id,
        business_id=business.id,
        channel="phone",
        current_node="completed",
        is_active=False,
        completed_at=datetime.now(timezone.utc),
        langgraph_thread_id=call_id,
    )
    db.add(conversation)
    await db.flush()

    # Store transcript as messages
    if transcript:
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="system",
            content=transcript,
            metadata_={
                "type": "transcript",
                "summary": summary,
                "ended_reason": ended_reason,
                "duration_seconds": duration_seconds,
            },
        )
        db.add(msg)

    lead.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    return {"status": "ok"}
