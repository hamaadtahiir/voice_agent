"""Vapi voice AI webhook routes."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    payload_type = body.get("type", "")
    logger.info("Vapi webhook: type=%s", payload_type)

    if payload_type == "assistant-request":
        return await _handle_assistant_request(body, db)
    elif payload_type == "function-call":
        return await _handle_function_call(body, db)
    elif payload_type == "end-of-call-report":
        return await _handle_end_of_call_report(body, db)
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

    # Build assistant config
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
        },
    ]

    return {
        "assistant": {
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt}
                ],
                "tools": tools,
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "21m00Tcm4TlvDq8ikWAM",
            },
            "firstMessage": first_message,
            "silenceTimeoutSeconds": 30,
            "maxDurationSeconds": 600,
        }
    }


async def _handle_function_call(body: dict, db: AsyncSession) -> dict:
    """Execute a tool call requested by the Vapi assistant."""
    function_call = body.get("functionCall", body.get("function_call", {}))
    fn_name = function_call.get("name", "")
    params = function_call.get("parameters", {})

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

    if fn_name == "check_availability":
        return await _fn_check_availability(params, business, db)
    elif fn_name == "book_appointment":
        return await _fn_book_appointment(params, business, db)
    else:
        return {"result": f"Unknown function: {fn_name}"}


async def _fn_check_availability(
    params: dict, business: Business | None, db: AsyncSession
) -> dict:
    """Check available appointment slots."""
    date_str = params.get("date", "")
    service_name = params.get("service_name")

    if not business:
        return {"result": "I'm sorry, I couldn't identify the business. Please try again."}

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
            return {
                "result": f"Available times on {date_str}: {', '.join(slot_strings)}"
            }
        else:
            return {
                "result": f"Sorry, there are no available slots on {date_str}. Would you like to try another date?"
            }
    except Exception:
        logger.exception("Error checking availability")
        return {
            "result": "I had trouble checking availability. Could you please try a different date?"
        }


async def _fn_book_appointment(
    params: dict, business: Business | None, db: AsyncSession
) -> dict:
    """Book an appointment and create lead record."""
    if not business:
        return {"result": "I'm sorry, I couldn't identify the business."}

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
        return {"result": "I couldn't parse that date and time. Please provide date as YYYY-MM-DD and time as HH:MM."}

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

    return {
        "result": f"Great! I've booked your appointment for {date_str} at {time_str}. "
        f"We look forward to seeing you, {name}!"
    }


async def _handle_end_of_call_report(body: dict, db: AsyncSession) -> dict:
    """Process end-of-call report: create/update lead and conversation records."""
    call_data = body.get("call", {})
    message_data = body.get("message", body)

    phone_number_id = call_data.get("phoneNumberId")
    caller_number = call_data.get("customer", {}).get("number", "")
    call_id = call_data.get("id", str(uuid.uuid4()))

    # Transcript and summary
    transcript = message_data.get("transcript", "")
    summary = message_data.get("summary", "")
    ended_reason = message_data.get("endedReason", "")
    duration_seconds = message_data.get("duration") or call_data.get("duration")

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
