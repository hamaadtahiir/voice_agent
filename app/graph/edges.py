"""Conditional edge functions that determine the next node in the conversation graph."""

from __future__ import annotations


def after_greeting(state: dict) -> str:
    """After greeting, ask for location."""
    return "ask_location"


def after_location(state: dict) -> str:
    """After collecting location, validate the service area."""
    return "validate_service_area"


def after_service_area_check(state: dict) -> str:
    """Route based on whether the lead is in the service area."""
    if state.get("in_service_area"):
        return "ask_pain_point"
    return "polite_decline"


def after_pain_point(state: dict) -> str:
    """After capturing the pain point, identify the matching service."""
    return "identify_service"


def after_identify_service(state: dict) -> str:
    """After identifying the service, decide the next step.

    - If the service is quotable, offer a quote first.
    - If media/photos would be useful, ask for media.
    - Otherwise, proceed to scheduling.
    """
    service_name = state.get("identified_service")
    if service_name:
        for svc in state.get("business_services") or []:
            if svc.get("name", "").lower() == service_name.lower() and svc.get("quotable"):
                return "offer_quote"

    if state.get("needs_media"):
        return "ask_media"
    return "ask_availability"


def after_quote(state: dict) -> str:
    """After presenting a quote, check if media is needed or go to scheduling."""
    if state.get("needs_media"):
        return "ask_media"
    return "ask_availability"


def after_media(state: dict) -> str:
    """After media collection, move to scheduling."""
    return "ask_availability"


def after_availability(state: dict) -> str:
    """After the customer shares availability, check the calendar."""
    return "check_calendar"


def after_calendar_check(state: dict) -> str:
    """After checking the calendar, present available slots."""
    return "suggest_slots"


def after_suggest_slots(state: dict) -> str:
    """After suggesting slots, confirm the booking."""
    return "confirm_booking"


def after_confirm(state: dict) -> str:
    """After the customer confirms, create the appointment."""
    return "create_appointment"


def after_appointment(state: dict) -> str:
    """After booking, notify the team."""
    return "notify_team"


def after_notify(state: dict) -> str:
    """After team notification, schedule reminders."""
    return "schedule_reminders"


def after_reminders(state: dict) -> str:
    """After reminders are queued, end the conversation."""
    return "done"


def after_decline(state: dict) -> str:
    """After declining an out-of-area lead, end the conversation."""
    return "done"
