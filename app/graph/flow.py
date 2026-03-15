"""Build and compile the LangGraph StateGraph for the conversation engine."""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from app.graph.edges import (
    after_appointment,
    after_availability,
    after_calendar_check,
    after_confirm,
    after_decline,
    after_greeting,
    after_identify_service,
    after_location,
    after_media,
    after_notify,
    after_pain_point,
    after_quote,
    after_reminders,
    after_service_area_check,
    after_suggest_slots,
)
from app.graph.nodes import (
    ask_availability_node,
    ask_location_node,
    ask_media_node,
    ask_pain_point_node,
    check_calendar_node,
    confirm_booking_node,
    create_appointment_node,
    done_node,
    greeting_node,
    identify_service_node,
    notify_team_node,
    offer_quote_node,
    polite_decline_node,
    schedule_reminders_node,
    suggest_slots_node,
    validate_service_area_node,
)
from app.graph.state import ConversationState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct the full conversation StateGraph with all nodes and edges."""
    graph = StateGraph(ConversationState)

    # -- Add nodes ----------------------------------------------------------
    graph.add_node("greeting", greeting_node)
    graph.add_node("ask_location", ask_location_node)
    graph.add_node("validate_service_area", validate_service_area_node)
    graph.add_node("ask_pain_point", ask_pain_point_node)
    graph.add_node("identify_service", identify_service_node)
    graph.add_node("offer_quote", offer_quote_node)
    graph.add_node("ask_media", ask_media_node)
    graph.add_node("ask_availability", ask_availability_node)
    graph.add_node("check_calendar", check_calendar_node)
    graph.add_node("suggest_slots", suggest_slots_node)
    graph.add_node("confirm_booking", confirm_booking_node)
    graph.add_node("create_appointment", create_appointment_node)
    graph.add_node("notify_team", notify_team_node)
    graph.add_node("schedule_reminders", schedule_reminders_node)
    graph.add_node("polite_decline", polite_decline_node)
    graph.add_node("done", done_node)

    # -- Set entry point ----------------------------------------------------
    graph.set_entry_point("greeting")

    # -- Conditional edges --------------------------------------------------
    graph.add_conditional_edges("greeting", after_greeting)
    graph.add_conditional_edges("ask_location", after_location)
    graph.add_conditional_edges("validate_service_area", after_service_area_check)
    graph.add_conditional_edges("ask_pain_point", after_pain_point)
    graph.add_conditional_edges("identify_service", after_identify_service)
    graph.add_conditional_edges("offer_quote", after_quote)
    graph.add_conditional_edges("ask_media", after_media)
    graph.add_conditional_edges("ask_availability", after_availability)
    graph.add_conditional_edges("check_calendar", after_calendar_check)
    graph.add_conditional_edges("suggest_slots", after_suggest_slots)
    graph.add_conditional_edges("confirm_booking", after_confirm)
    graph.add_conditional_edges("create_appointment", after_appointment)
    graph.add_conditional_edges("notify_team", after_notify)
    graph.add_conditional_edges("schedule_reminders", after_reminders)
    graph.add_conditional_edges("polite_decline", after_decline)

    # -- Terminal edge ------------------------------------------------------
    graph.add_edge("done", END)

    return graph


# Compile once at module level
compiled_graph = build_graph().compile()


async def run_graph(
    state: ConversationState | dict,
    user_message: str | None = None,
) -> dict:
    """Run (or resume) the conversation graph.

    If ``user_message`` is provided it is appended to ``messages`` before
    invoking the graph.  Returns the fully updated state dict.
    """
    # Ensure state is a mutable dict
    working_state = dict(state)
    working_state.setdefault("messages", [])

    if user_message:
        working_state["messages"] = list(working_state["messages"]) + [
            HumanMessage(content=user_message)
        ]

    try:
        result = await compiled_graph.ainvoke(working_state)
        return result
    except Exception:
        logger.exception("Error running conversation graph")
        # Return state with a fallback message so the caller always has
        # something to respond with.
        from langchain_core.messages import AIMessage

        working_state["messages"] = list(working_state["messages"]) + [
            AIMessage(content="I apologize, but I'm experiencing a technical issue. Please try again in a moment.")
        ]
        return working_state
