"""LangGraph conversation state definition."""

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class ConversationState(TypedDict):
    """Typed state that flows through every node of the conversation graph.

    The ``messages`` field uses LangGraph's ``add_messages`` reducer so that
    returning a list of new messages from a node automatically appends them
    to the existing list.
    """

    messages: Annotated[list, add_messages]

    # Business context
    business_id: str
    business_name: str
    business_industry: str
    business_timezone: str
    business_services: list[dict]
    business_service_areas: list
    business_hours: dict
    welcome_message: str
    system_prompt: str

    # Channel
    channel: str

    # Lead info (progressively filled)
    lead_id: str
    lead_name: Optional[str]
    lead_phone: Optional[str]
    lead_email: Optional[str]
    lead_location_zip: Optional[str]
    lead_location_city: Optional[str]
    lead_location_state: Optional[str]

    # Qualification
    in_service_area: Optional[bool]
    pain_point: Optional[str]
    identified_service: Optional[str]

    # Scheduling
    available_slots: Optional[list[dict]]
    selected_slot: Optional[dict]
    appointment_id: Optional[str]

    # Quote
    quote_range: Optional[dict]

    # Flow control
    current_node: str
    needs_media: bool
    media_urls: list[str]
    conversation_id: str
