from typing import Optional

from pydantic import BaseModel


class WhatsAppMessage(BaseModel):
    from_number: str
    message_body: str
    message_type: str = "text"
    media_url: Optional[str] = None
    timestamp: Optional[str] = None


class VapiPayload(BaseModel):
    type: str
    call: Optional[dict] = None
    function_call: Optional[dict] = None
    message: Optional[dict] = None


class ChatMessage(BaseModel):
    content: str
    media_url: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    node: Optional[str] = None
    is_complete: bool = False
