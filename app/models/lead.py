import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.business import Business
    from app.models.conversation import Conversation


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("business_id", "external_id", "channel", name="uq_lead_external"),
        Index("ix_lead_business_status", "business_id", "status"),
        Index("ix_lead_business_created", "business_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(50))  # web_chat, whatsapp, phone, email

    # Contact info
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)

    # Location
    location_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Qualification
    pain_point: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identified_service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="new",
    )  # new, qualifying, qualified, appointment_booked, appointment_completed, lost, out_of_area

    # Media
    media_urls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Tracking
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Engagement tracking
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    drop_off_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    re_engagement_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    re_engagement_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    business: Mapped["Business"] = relationship(back_populates="leads")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="lead",
        lazy="selectin",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="lead",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Lead {self.id} channel={self.channel} status={self.status}>"
