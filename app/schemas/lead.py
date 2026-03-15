import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    channel: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location_zip: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    pain_point: Optional[str] = None
    identified_service: Optional[str] = None
    score: Optional[int] = None
    score_breakdown: Optional[dict] = None
    status: str
    media_urls: Optional[list] = None
    source_url: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None
