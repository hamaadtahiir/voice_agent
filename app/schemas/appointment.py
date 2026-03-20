import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    lead_id: uuid.UUID
    business_id: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int = 60
    service_name: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    lead_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    scheduled_at: datetime
    duration_minutes: int
    service_name: Optional[str] = None
    google_event_id: Optional[str] = None
    google_event_link: Optional[str] = None
    status: str
    reminder_24h_sent: bool
    reminder_1h_sent: bool
    reminder_24h_sent_at: Optional[datetime] = None
    reminder_1h_sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    lead_name: Optional[str] = None


class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
