import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ServiceConfig(BaseModel):
    name: str
    duration_min: int = 60
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    quotable: bool = False


class BusinessHours(BaseModel):
    day: str
    open: str = "09:00"
    close: str = "17:00"
    is_closed: bool = False


class BrandingConfig(BaseModel):
    primary_color: str = "#2563eb"
    logo_url: Optional[str] = None
    welcome_message: str = "Hi! How can we help you today?"


class BusinessCreate(BaseModel):
    name: str
    slug: str
    industry: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: str = "America/New_York"
    service_areas: Optional[list] = None
    business_hours: Optional[list[BusinessHours]] = None
    services: Optional[list[ServiceConfig]] = None
    branding: Optional[BrandingConfig] = None
    appointment_duration_default: int = 60


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    industry: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: Optional[str] = None
    service_areas: Optional[list] = None
    business_hours: Optional[list[BusinessHours]] = None
    services: Optional[list[ServiceConfig]] = None
    branding: Optional[BrandingConfig] = None
    appointment_duration_default: Optional[int] = None
    system_prompt_override: Optional[str] = None
    qualification_questions: Optional[list] = None
    is_active: Optional[bool] = None


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    industry: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: str
    service_areas: Optional[list] = None
    business_hours: Optional[dict] = None
    services: Optional[list] = None
    branding: Optional[dict] = None
    google_calendar_id: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    notification_emails: Optional[list] = None
    notification_phone: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    vapi_assistant_id: Optional[str] = None
    vapi_phone_number_id: Optional[str] = None
    system_prompt_override: Optional[str] = None
    qualification_questions: Optional[list] = None
    appointment_duration_default: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
