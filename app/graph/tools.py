"""LangGraph tool definitions (OpenAI function-calling format) and handlers.

Tool handlers receive the current graph *state* as a first positional
argument plus any keyword arguments extracted from the LLM's tool call.
They return a result dict (or string) that is fed back to the model.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI function-calling tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_service_area",
            "description": (
                "Check if a location (zip code or city/state) is within "
                "the business's service area"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zip_code": {"type": "string", "description": "Customer zip code"},
                    "city": {"type": "string", "description": "Customer city"},
                    "state": {"type": "string", "description": "Customer state"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Get available appointment time slots for a given date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
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
            "description": "Book an appointment at the selected time slot",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_start_iso": {
                        "type": "string",
                        "description": "ISO format start time of the selected slot",
                    },
                    "service_name": {"type": "string", "description": "Name of the service"},
                    "customer_name": {"type": "string", "description": "Customer name"},
                    "customer_phone": {"type": "string", "description": "Customer phone number"},
                    "customer_email": {"type": "string", "description": "Customer email address"},
                },
                "required": ["slot_start_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_lead_info",
            "description": "Save or update lead contact information and details",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Customer name"},
                    "phone": {"type": "string", "description": "Customer phone number"},
                    "email": {"type": "string", "description": "Customer email address"},
                    "zip_code": {"type": "string", "description": "Customer zip code"},
                    "city": {"type": "string", "description": "Customer city"},
                    "state": {"type": "string", "description": "Customer state"},
                    "pain_point": {"type": "string", "description": "Customer's described need or issue"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quote_range",
            "description": "Get an instant price quote range for a service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to quote",
                    },
                },
                "required": ["service_name"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handler functions
# ---------------------------------------------------------------------------

def check_service_area(
    state: dict,
    zip_code: str | None = None,
    city: str | None = None,
    state_name: str | None = None,
    **kwargs: Any,
) -> dict:
    """Check whether the given location falls within the business service areas.

    The ``state`` parameter carries ``business_service_areas`` which is
    typically a list of zip codes and/or city names.
    """
    # Accept 'state' kwarg from LLM as state_name
    if "state" in kwargs and state_name is None:
        state_name = kwargs.pop("state")

    service_areas: list = state.get("business_service_areas") or []
    if not service_areas:
        # No areas configured means the business serves everywhere
        return {"in_service_area": True, "message": "Service area not restricted."}

    # Normalise the service areas for comparison
    normalised_areas = [str(a).strip().lower() for a in service_areas]

    # Check zip code
    if zip_code:
        if zip_code.strip().lower() in normalised_areas:
            return {"in_service_area": True, "message": f"Zip code {zip_code} is in the service area."}

    # Check city
    if city:
        city_lower = city.strip().lower()
        for area in normalised_areas:
            if city_lower in area or area in city_lower:
                return {"in_service_area": True, "message": f"{city} is in the service area."}

    # Check city + state combo
    if city and state_name:
        combo = f"{city.strip().lower()}, {state_name.strip().lower()}"
        for area in normalised_areas:
            if combo in area or area in combo:
                return {"in_service_area": True, "message": f"{city}, {state_name} is in the service area."}

    location_desc = zip_code or f"{city or ''}, {state_name or ''}"
    return {
        "in_service_area": False,
        "message": f"Unfortunately, {location_desc.strip(', ')} is outside our service area.",
    }


async def get_available_slots_handler(state: dict, date: str, **kwargs: Any) -> dict:
    """Fetch available calendar slots for the given date.

    This is async because it calls the calendar service.
    """
    from app.services.calendar_service import get_available_slots

    # We need the business object. Build a minimal stand-in from state.
    from types import SimpleNamespace

    business = SimpleNamespace(
        id=state.get("business_id"),
        timezone=state.get("business_timezone", "America/New_York"),
        business_hours=state.get("business_hours"),
        google_oauth_token=None,  # Credentials are loaded inside the service
        google_calendar_id=None,
        appointment_duration_default=60,
    )

    # Try to get the actual business from DB for real credentials
    try:
        from sqlalchemy import select as sa_select
        from app.db.engine import async_session_factory
        from app.models.business import Business
        import uuid

        async with async_session_factory() as db:
            result = await db.execute(
                sa_select(Business).where(Business.id == uuid.UUID(state["business_id"]))
            )
            db_business = result.scalar_one_or_none()
            if db_business:
                business = db_business
    except Exception:
        logger.debug("Could not load business from DB for calendar check; using state data")

    duration = 60
    # Find the duration from the identified service
    identified = state.get("identified_service")
    if identified:
        for svc in (state.get("business_services") or []):
            if svc.get("name", "").lower() == identified.lower():
                duration = svc.get("duration_min", 60)
                break

    slots = await get_available_slots(business, date, duration_minutes=duration)

    if slots:
        return {
            "available": True,
            "date": date,
            "slots": slots,
            "message": f"Found {len(slots)} available slot(s) on {date}.",
        }
    return {
        "available": False,
        "date": date,
        "slots": [],
        "message": f"No available slots on {date}. Please try another date.",
    }


async def book_appointment_handler(
    state: dict,
    slot_start_iso: str,
    service_name: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_email: str | None = None,
    **kwargs: Any,
) -> dict:
    """Create an appointment in the database and optionally on Google Calendar."""
    import uuid
    from datetime import datetime

    from sqlalchemy import select as sa_select

    from app.db.engine import async_session_factory
    from app.models.appointment import Appointment
    from app.models.business import Business
    from app.models.lead import Lead
    from app.services.calendar_service import create_calendar_event

    service = service_name or state.get("identified_service") or "General"
    name = customer_name or state.get("lead_name")
    phone = customer_phone or state.get("lead_phone")
    email = customer_email or state.get("lead_email")

    try:
        scheduled_at = datetime.fromisoformat(slot_start_iso)
    except ValueError:
        return {"success": False, "message": f"Invalid date/time format: {slot_start_iso}"}

    # Determine duration
    duration = 60
    for svc in (state.get("business_services") or []):
        if svc.get("name", "").lower() == service.lower():
            duration = svc.get("duration_min", 60)
            break

    try:
        async with async_session_factory() as db:
            # Load business and lead
            biz_result = await db.execute(
                sa_select(Business).where(Business.id == uuid.UUID(state["business_id"]))
            )
            business = biz_result.scalar_one_or_none()

            lead_result = await db.execute(
                sa_select(Lead).where(Lead.id == uuid.UUID(state["lead_id"]))
            )
            lead = lead_result.scalar_one_or_none()

            if not business or not lead:
                return {"success": False, "message": "Business or lead not found."}

            # Update lead info if provided
            if name and not lead.name:
                lead.name = name
            if phone and not lead.phone:
                lead.phone = phone
            if email and not lead.email:
                lead.email = email

            # Create appointment
            appointment = Appointment(
                business_id=business.id,
                lead_id=lead.id,
                conversation_id=uuid.UUID(state["conversation_id"]) if state.get("conversation_id") else None,
                scheduled_at=scheduled_at,
                duration_minutes=duration,
                service_name=service,
                status="scheduled",
            )
            db.add(appointment)
            await db.flush()

            # Create Google Calendar event
            cal_result = await create_calendar_event(
                business,
                lead,
                {
                    "scheduled_at": scheduled_at,
                    "duration_minutes": duration,
                    "service_name": service,
                },
            )
            if cal_result:
                appointment.google_event_id = cal_result.get("event_id")
                appointment.google_event_link = cal_result.get("event_link")

            # Update lead status
            lead.status = "appointment_booked"
            lead.identified_service = service

            await db.commit()

            return {
                "success": True,
                "appointment_id": str(appointment.id),
                "scheduled_at": scheduled_at.isoformat(),
                "service_name": service,
                "duration_minutes": duration,
                "google_event_link": cal_result.get("event_link", ""),
                "message": (
                    f"Appointment booked for {service} on "
                    f"{scheduled_at.strftime('%A, %B %d at %-I:%M %p')}."
                ),
            }

    except Exception:
        logger.exception("Failed to book appointment")
        return {"success": False, "message": "There was an error booking the appointment. Please try again."}


def save_lead_info(state: dict, **kwargs: Any) -> dict:
    """Save lead contact information into the state.

    This handler returns the fields to be merged into the graph state by
    the calling node.
    """
    updates: dict[str, Any] = {}
    field_map = {
        "name": "lead_name",
        "phone": "lead_phone",
        "email": "lead_email",
        "zip_code": "lead_location_zip",
        "city": "lead_location_city",
        "state": "lead_location_state",
        "pain_point": "pain_point",
    }

    saved_fields = []
    for kwarg_key, state_key in field_map.items():
        value = kwargs.get(kwarg_key)
        if value:
            updates[state_key] = value
            saved_fields.append(kwarg_key)

    if saved_fields:
        return {
            "saved": True,
            "fields": saved_fields,
            "updates": updates,
            "message": f"Saved: {', '.join(saved_fields)}.",
        }
    return {"saved": False, "message": "No information provided to save."}


def get_quote_range(state: dict, service_name: str, **kwargs: Any) -> dict:
    """Get a price quote range for the named service."""
    from app.services.quote import calculate_quote_range

    services = state.get("business_services") or []
    matched_service = None
    for svc in services:
        if svc.get("name", "").lower() == service_name.lower():
            matched_service = svc
            break

    if not matched_service:
        # Try partial match
        for svc in services:
            if service_name.lower() in svc.get("name", "").lower():
                matched_service = svc
                break

    if not matched_service:
        return {
            "quotable": False,
            "message": f"Service '{service_name}' not found. Available services: "
                       + ", ".join(s.get("name", "") for s in services),
        }

    quote = calculate_quote_range(matched_service)
    if quote:
        return {
            "quotable": True,
            "service_name": quote["service_name"],
            "price_min": quote["min"],
            "price_max": quote["max"],
            "message": (
                f"{quote['service_name']} typically ranges from "
                f"${quote['min']:,.2f} to ${quote['max']:,.2f}. "
                f"A precise quote requires an on-site assessment."
            ),
        }
    return {
        "quotable": False,
        "message": f"{matched_service.get('name', service_name)} is not quotable online. "
                   "An on-site assessment is required for accurate pricing.",
    }
