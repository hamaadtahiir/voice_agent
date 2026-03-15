import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.conversation import Conversation
    from app.models.lead import Lead


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    industry: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")

    # Configuration stored as JSON
    service_areas: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    business_hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    services: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    branding: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Google Calendar integration
    google_oauth_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_calendar_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notifications
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notification_emails: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    notification_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # WhatsApp integration
    whatsapp_phone_number_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    whatsapp_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Vapi (Voice AI) integration
    vapi_assistant_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vapi_phone_number_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # AI / Conversation customisation
    system_prompt_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qualification_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    appointment_duration_default: Mapped[int] = mapped_column(Integer, default=60)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    leads: Mapped[list["Lead"]] = relationship(
        back_populates="business",
        lazy="selectin",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="business",
        lazy="selectin",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="business",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Business {self.slug}>"
