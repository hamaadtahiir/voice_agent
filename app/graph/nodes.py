"""Node functions for the LangGraph conversation flow.

Each node:
1. Gets the system prompt for its stage.
2. Calls the LLM with the conversation history and (optionally) tools.
3. Processes any tool calls and merges results into state.
4. Returns a dict of state updates (including new ``messages``).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.prompts import get_system_prompt
from app.graph.tools import (
    TOOL_DEFINITIONS,
    book_appointment_handler,
    check_service_area,
    get_available_slots_handler,
    get_quote_range,
    save_lead_info,
)
from app.services.llm import call_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _messages_to_openai(state: dict) -> list[dict]:
    """Convert LangChain message objects in state to OpenAI-format dicts."""
    out: list[dict] = []
    for m in state.get("messages", []):
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            out.append({"role": "assistant", "content": m.content})
        elif isinstance(m, dict):
            out.append(m)
        elif hasattr(m, "type"):
            role_map = {"human": "user", "ai": "assistant", "system": "system"}
            out.append({
                "role": role_map.get(m.type, "user"),
                "content": getattr(m, "content", ""),
            })
    return out


async def _llm_node(
    state: dict,
    node_name: str,
    tools: list[dict] | None = None,
    extra_state_updates: dict | None = None,
) -> dict:
    """Generic LLM-calling helper used by most nodes.

    1. Builds the OpenAI message list with system prompt.
    2. Calls the LLM (with optional tools).
    3. Handles a single round of tool calls.
    4. Returns a state-update dict.
    """
    system_prompt = get_system_prompt(node_name, state)
    openai_messages = [{"role": "system", "content": system_prompt}] + _messages_to_openai(state)

    response = await call_llm(openai_messages, tools=tools)

    state_updates: dict[str, Any] = {"current_node": node_name}
    if extra_state_updates:
        state_updates.update(extra_state_updates)

    # Handle tool calls if present
    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            result = await _execute_tool(fn_name, state, args)

            # Merge tool-returned state updates
            if isinstance(result, dict):
                updates = result.get("updates")
                if updates and isinstance(updates, dict):
                    state_updates.update(updates)

                # Specific field merges
                if "in_service_area" in result:
                    state_updates["in_service_area"] = result["in_service_area"]
                if "slots" in result:
                    state_updates["available_slots"] = result["slots"]
                if "appointment_id" in result:
                    state_updates["appointment_id"] = result["appointment_id"]
                if "quotable" in result and result.get("price_min") is not None:
                    state_updates["quote_range"] = {
                        "min": result["price_min"],
                        "max": result["price_max"],
                        "service_name": result.get("service_name", ""),
                    }

        # After tool calls, call LLM again for the user-facing response
        # Append tool results to the messages
        tool_summary_parts = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = await _execute_tool(tc.function.name, {**state, **state_updates}, args)
            summary = result.get("message", json.dumps(result)) if isinstance(result, dict) else str(result)
            tool_summary_parts.append(summary)

        tool_context = "\n".join(tool_summary_parts)
        openai_messages.append({
            "role": "assistant",
            "content": f"[Tool results: {tool_context}]",
        })
        openai_messages.append({
            "role": "system",
            "content": f"Based on these tool results, provide a natural response to the customer: {tool_context}",
        })

        follow_up = await call_llm(openai_messages)
        text = getattr(follow_up, "content", "") or ""
    else:
        text = getattr(response, "content", "") or ""

    state_updates["messages"] = [AIMessage(content=text)]
    return state_updates


async def _execute_tool(fn_name: str, state: dict, args: dict) -> Any:
    """Dispatch a tool call to the appropriate handler."""
    if fn_name == "check_service_area":
        # The LLM may send 'state' as a key (the US state), rename to avoid
        # shadowing the graph state parameter.
        if "state" in args:
            args["state_name"] = args.pop("state")
        return check_service_area(state, **args)
    elif fn_name == "get_available_slots":
        return await get_available_slots_handler(state, **args)
    elif fn_name == "book_appointment":
        return await book_appointment_handler(state, **args)
    elif fn_name == "save_lead_info":
        return save_lead_info(state, **args)
    elif fn_name == "get_quote_range":
        return get_quote_range(state, **args)
    else:
        return {"error": f"Unknown tool: {fn_name}"}


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def greeting_node(state: dict) -> dict:
    """Generate the initial greeting. Uses the business welcome message
    directly instead of calling the LLM.
    """
    welcome = state.get("welcome_message") or (
        f"Welcome to {state.get('business_name', 'our company')}! "
        "How can we help you today?"
    )
    return {
        "messages": [AIMessage(content=welcome)],
        "current_node": "greeting",
    }


async def ask_location_node(state: dict) -> dict:
    """Ask for location; handle save_lead_info if the user already provided it."""
    tools = [
        t for t in TOOL_DEFINITIONS if t["function"]["name"] == "save_lead_info"
    ]
    return await _llm_node(state, "ask_location", tools=tools)


async def validate_service_area_node(state: dict) -> dict:
    """Check if the lead is in the service area."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] in ("check_service_area", "save_lead_info")
    ]

    # If we already have location info, run the check directly
    zip_code = state.get("lead_location_zip")
    city = state.get("lead_location_city")
    state_name = state.get("lead_location_state")

    extra: dict[str, Any] = {}
    if zip_code or city:
        result = check_service_area(state, zip_code=zip_code, city=city, state_name=state_name)
        extra["in_service_area"] = result.get("in_service_area", False)

    return await _llm_node(state, "validate_service_area", tools=tools, extra_state_updates=extra)


async def ask_pain_point_node(state: dict) -> dict:
    """Ask about the customer's issue/need."""
    tools = [
        t for t in TOOL_DEFINITIONS if t["function"]["name"] == "save_lead_info"
    ]
    return await _llm_node(state, "ask_pain_point", tools=tools)


async def identify_service_node(state: dict) -> dict:
    """Match the pain point to available services."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] in ("save_lead_info", "get_quote_range")
    ]

    result = await _llm_node(state, "identify_service", tools=tools)

    # Determine if media would be helpful based on industry
    industry = (state.get("business_industry") or "").lower()
    media_industries = {"roofing", "remodeling", "construction", "landscaping",
                        "plumbing", "painting", "flooring", "hvac", "home improvement",
                        "contracting", "renovation"}
    if any(ind in industry for ind in media_industries):
        result["needs_media"] = True
    else:
        result.setdefault("needs_media", False)

    return result


async def offer_quote_node(state: dict) -> dict:
    """Show quote range for quotable services."""
    tools = [
        t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_quote_range"
    ]

    # Pre-fetch quote if service is identified
    service_name = state.get("identified_service")
    extra: dict[str, Any] = {}
    if service_name:
        quote_result = get_quote_range(state, service_name)
        if quote_result.get("quotable"):
            extra["quote_range"] = {
                "min": quote_result["price_min"],
                "max": quote_result["price_max"],
                "service_name": quote_result["service_name"],
            }

    return await _llm_node(state, "offer_quote", tools=tools, extra_state_updates=extra)


async def ask_media_node(state: dict) -> dict:
    """Ask for photos if applicable."""
    return await _llm_node(state, "ask_media")


async def ask_availability_node(state: dict) -> dict:
    """Ask preferred date/time."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] == "get_available_slots"
    ]
    return await _llm_node(state, "ask_availability", tools=tools)


async def check_calendar_node(state: dict) -> dict:
    """Fetch available slots from calendar."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] == "get_available_slots"
    ]
    return await _llm_node(state, "check_calendar", tools=tools)


async def suggest_slots_node(state: dict) -> dict:
    """Present available time slots to the user."""
    # Include slot data in the system prompt context
    slots = state.get("available_slots") or []
    extra: dict[str, Any] = {}

    if slots:
        # Add slots info to the state so the prompt can reference it
        slots_text = "\n".join(
            f"  - {s.get('start', '?')} to {s.get('end', '?')}"
            for s in slots[:8]
        )
        extra_msg = f"\n\nAvailable time slots:\n{slots_text}"
    else:
        extra_msg = "\n\nNo time slots are currently available."

    # Temporarily augment the welcome message to carry slot info
    # (the system prompt will include this context)
    original_welcome = state.get("welcome_message", "")
    state_copy = dict(state)
    state_copy["welcome_message"] = original_welcome + extra_msg

    return await _llm_node(state_copy, "suggest_slots")


async def confirm_booking_node(state: dict) -> dict:
    """Confirm the selected slot and collect any missing info."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] in ("save_lead_info", "book_appointment")
    ]
    return await _llm_node(state, "confirm_booking", tools=tools)


async def create_appointment_node(state: dict) -> dict:
    """Book the appointment and create a calendar event."""
    tools = [
        t for t in TOOL_DEFINITIONS
        if t["function"]["name"] == "book_appointment"
    ]

    # If we have a selected slot, try to book directly
    selected = state.get("selected_slot")
    extra: dict[str, Any] = {}
    if selected and selected.get("start_iso"):
        result = await book_appointment_handler(
            state,
            slot_start_iso=selected["start_iso"],
            service_name=state.get("identified_service"),
            customer_name=state.get("lead_name"),
            customer_phone=state.get("lead_phone"),
            customer_email=state.get("lead_email"),
        )
        if result.get("success"):
            extra["appointment_id"] = result["appointment_id"]

    return await _llm_node(state, "create_appointment", tools=tools, extra_state_updates=extra)


async def notify_team_node(state: dict) -> dict:
    """Send notifications to the business team about the new booking."""
    # Trigger notifications asynchronously
    appointment_id = state.get("appointment_id")
    if appointment_id:
        try:
            import uuid
            from sqlalchemy import select as sa_select
            from app.db.engine import async_session_factory
            from app.models.appointment import Appointment
            from app.models.business import Business
            from app.models.lead import Lead
            from app.services.notifications import notify_team_new_booking

            async with async_session_factory() as db:
                appt_result = await db.execute(
                    sa_select(Appointment).where(Appointment.id == uuid.UUID(appointment_id))
                )
                appointment = appt_result.scalar_one_or_none()
                biz_result = await db.execute(
                    sa_select(Business).where(Business.id == uuid.UUID(state["business_id"]))
                )
                business = biz_result.scalar_one_or_none()
                lead_result = await db.execute(
                    sa_select(Lead).where(Lead.id == uuid.UUID(state["lead_id"]))
                )
                lead = lead_result.scalar_one_or_none()

                if appointment and business and lead:
                    await notify_team_new_booking(business, lead, appointment, db)
        except Exception:
            logger.exception("Failed to send team notifications")

    return await _llm_node(state, "notify_team")


async def schedule_reminders_node(state: dict) -> dict:
    """Mark reminders to be scheduled (the APScheduler job handles actual sending)."""
    return await _llm_node(state, "schedule_reminders")


async def polite_decline_node(state: dict) -> dict:
    """Politely decline out-of-area leads."""
    # Update lead status
    try:
        import uuid
        from sqlalchemy import select as sa_select
        from app.db.engine import async_session_factory
        from app.models.lead import Lead

        async with async_session_factory() as db:
            lead_result = await db.execute(
                sa_select(Lead).where(Lead.id == uuid.UUID(state["lead_id"]))
            )
            lead = lead_result.scalar_one_or_none()
            if lead:
                lead.status = "out_of_area"
                await db.commit()
    except Exception:
        logger.exception("Failed to update lead status to out_of_area")

    return await _llm_node(state, "polite_decline")


async def done_node(state: dict) -> dict:
    """Conversation complete. Mark conversation as inactive."""
    try:
        import uuid
        from sqlalchemy import select as sa_select
        from datetime import datetime, timezone
        from app.db.engine import async_session_factory
        from app.models.conversation import Conversation

        async with async_session_factory() as db:
            conv_result = await db.execute(
                sa_select(Conversation).where(
                    Conversation.id == uuid.UUID(state["conversation_id"])
                )
            )
            convo = conv_result.scalar_one_or_none()
            if convo:
                convo.is_active = False
                convo.completed_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception:
        logger.exception("Failed to mark conversation as complete")

    # Score the lead
    try:
        import uuid
        from sqlalchemy import select as sa_select
        from app.db.engine import async_session_factory
        from app.models.lead import Lead
        from app.services.lead_scoring import score_lead

        async with async_session_factory() as db:
            lead_result = await db.execute(
                sa_select(Lead).where(Lead.id == uuid.UUID(state["lead_id"]))
            )
            lead = lead_result.scalar_one_or_none()
            if lead:
                lead_data = {
                    "name": lead.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "in_service_area": state.get("in_service_area"),
                    "pain_point": lead.pain_point,
                    "identified_service": lead.identified_service,
                    "media_urls": lead.media_urls,
                }
                score, breakdown = score_lead(lead_data)
                lead.score = score
                lead.score_breakdown = breakdown
                await db.commit()
    except Exception:
        logger.exception("Failed to score lead")

    return await _llm_node(state, "done")
