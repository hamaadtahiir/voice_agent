import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    media_url: Optional[str] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    current_node: Optional[str] = None
    is_active: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    messages: list[MessageResponse] = []
