"""System prompts for each conversation graph node."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.graph.state import ConversationState


def _services_text(state: dict) -> str:
    """Format the business services list for inclusion in prompts."""
    services = state.get("business_services") or []
    if not services:
        return "No specific services listed."
    lines = []
    for s in services:
        name = s.get("name", "Unknown")
        duration = s.get("duration_min", "?")
        price_range = ""
        if s.get("price_min") is not None and s.get("price_max") is not None:
            price_range = f" (${s['price_min']} - ${s['price_max']})"
        elif s.get("price_min") is not None:
            price_range = f" (from ${s['price_min']})"
        lines.append(f"- {name}: ~{duration} min{price_range}")
    return "\n".join(lines)


def _service_areas_text(state: dict) -> str:
    """Format service areas for inclusion in prompts."""
    areas = state.get("business_service_areas") or []
    if not areas:
        return "No specific service areas defined."
    return ", ".join(str(a) for a in areas)


def _business_hours_text(state: dict) -> str:
    """Format business hours for inclusion in prompts."""
    hours = state.get("business_hours") or {}
    if not hours:
        return "Monday-Friday, 9:00 AM - 5:00 PM"
    lines = []
    for day, times in hours.items():
        if isinstance(times, dict):
            lines.append(f"{day.capitalize()}: {times.get('open', '9:00')} - {times.get('close', '17:00')}")
        else:
            lines.append(f"{day.capitalize()}: {times}")
    return "\n".join(lines)


def _base_context(state: dict) -> str:
    """Return the shared business context block."""
    return (
        f"Business: {state.get('business_name', 'Our Company')}\n"
        f"Industry: {state.get('business_industry', 'General')}\n"
        f"Timezone: {state.get('business_timezone', 'America/New_York')}\n"
        f"Services offered:\n{_services_text(state)}\n"
        f"Service areas: {_service_areas_text(state)}\n"
        f"Business hours:\n{_business_hours_text(state)}"
    )


def get_system_prompt(node: str, state: dict) -> str:
    """Return the system prompt appropriate for the given conversation node."""
    context = _base_context(state)
    custom_prompt = state.get("system_prompt", "")

    prompts = {
        "greeting": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"You are greeting a new visitor. Be warm and professional. "
            f"Welcome them to {state.get('business_name', 'our company')} and "
            f"ask how you can help them today. Keep it brief and friendly."
        ),
        "ask_location": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"You need to determine the customer's location to check if they are "
            f"in the service area. Ask for their zip code or city and state. "
            f"Be natural and conversational - for example: 'To make sure we can "
            f"help you, could you share your zip code or city?'\n\n"
            f"If the user has already mentioned a location, use the save_lead_info "
            f"tool to save it. If they provide a zip code, city, or state, save it."
        ),
        "validate_service_area": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Check if the customer's location is within the service area using "
            f"the check_service_area tool. The service areas are: "
            f"{_service_areas_text(state)}.\n"
            f"If they are in the area, let them know and move on. "
            f"If not, politely explain."
        ),
        "ask_pain_point": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Ask the customer what specific issue, project, or service they need "
            f"help with. Be empathetic and curious. Ask follow-up questions if "
            f"their response is vague. The available services are:\n"
            f"{_services_text(state)}\n\n"
            f"Use the save_lead_info tool to record their pain point once described."
        ),
        "identify_service": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Based on the customer's described need, identify which of the "
            f"following services best matches:\n{_services_text(state)}\n\n"
            f"Confirm with the customer that you've understood their need correctly. "
            f"Use the save_lead_info tool to record the identified service.\n"
            f"Determine if this type of work would benefit from photos (e.g., "
            f"roofing damage, remodeling projects, landscaping)."
        ),
        "offer_quote": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Present the customer with a price range estimate for the identified "
            f"service. Use the get_quote_range tool to get the range. Present it "
            f"naturally: 'Based on what you've described, this type of work "
            f"typically ranges from $X to $Y.' Emphasise that a precise quote "
            f"requires an on-site assessment."
        ),
        "ask_media": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Ask the customer if they can share any photos of the area or issue "
            f"they need help with. Explain that photos help provide a more accurate "
            f"estimate and prepare for the visit. Be understanding if they don't "
            f"have any available. Keep it optional and friendly."
        ),
        "ask_availability": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Ask the customer what dates and times work best for them for an "
            f"appointment. Mention the business hours:\n{_business_hours_text(state)}\n\n"
            f"Be flexible and accommodating. If they mention a specific date, use "
            f"the get_available_slots tool to check availability."
        ),
        "check_calendar": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Use the get_available_slots tool to find open time slots for the "
            f"customer's preferred date. If no slots are available, suggest the "
            f"next available day."
        ),
        "suggest_slots": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Present the available time slots to the customer in a clear, easy-to-read "
            f"format. Offer 3-5 options if available. Ask which time works best for them. "
            f"Be helpful and flexible."
        ),
        "confirm_booking": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Confirm the appointment details with the customer before booking:\n"
            f"- Service\n"
            f"- Date and time\n"
            f"- Their name and contact info\n\n"
            f"Ask for any missing contact information (name, phone, email). "
            f"Use the save_lead_info tool to save any new contact info. "
            f"Once everything is confirmed, use the book_appointment tool."
        ),
        "create_appointment": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"The appointment is being booked. Confirm the booking to the customer "
            f"with all the details. Let them know they'll receive a confirmation "
            f"and reminders. Thank them for choosing {state.get('business_name', 'us')}."
        ),
        "notify_team": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"The team has been notified. Reassure the customer that everything is "
            f"set and someone from the team will be ready for their appointment."
        ),
        "schedule_reminders": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"Let the customer know they'll receive reminders before their appointment "
            f"(24 hours and 1 hour before). Ask if there's anything else they need."
        ),
        "polite_decline": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"The customer is outside the service area. Politely and empathetically "
            f"explain that {state.get('business_name', 'we')} currently only serves: "
            f"{_service_areas_text(state)}. Apologise for the inconvenience and "
            f"suggest they look for a local provider. Wish them well."
        ),
        "done": (
            f"{custom_prompt}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"INSTRUCTIONS:\n"
            f"The conversation is wrapping up. Thank the customer and let them know "
            f"they can reach out again any time if they need anything else."
        ),
    }

    return prompts.get(node, prompts["greeting"])
