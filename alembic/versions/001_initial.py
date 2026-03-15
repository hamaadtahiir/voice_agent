"""Initial schema - all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-03-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- admins ---
    op.create_table(
        "admins",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="support"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- businesses ---
    op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column(
            "timezone", sa.String(50), nullable=False, server_default="America/New_York"
        ),
        sa.Column("service_areas", sa.JSON(), nullable=True),
        sa.Column("business_hours", sa.JSON(), nullable=True),
        sa.Column("services", sa.JSON(), nullable=True),
        sa.Column("branding", sa.JSON(), nullable=True),
        sa.Column("google_oauth_token", sa.Text(), nullable=True),
        sa.Column("google_calendar_id", sa.String(255), nullable=True),
        sa.Column("slack_webhook_url", sa.String(500), nullable=True),
        sa.Column("notification_emails", sa.JSON(), nullable=True),
        sa.Column("notification_phone", sa.String(30), nullable=True),
        sa.Column("whatsapp_phone_number_id", sa.String(100), nullable=True),
        sa.Column("whatsapp_access_token", sa.Text(), nullable=True),
        sa.Column("vapi_assistant_id", sa.String(255), nullable=True),
        sa.Column("vapi_phone_number_id", sa.String(255), nullable=True),
        sa.Column("system_prompt_override", sa.Text(), nullable=True),
        sa.Column("qualification_questions", sa.JSON(), nullable=True),
        sa.Column(
            "appointment_duration_default",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- leads ---
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("location_zip", sa.String(20), nullable=True),
        sa.Column("location_city", sa.String(100), nullable=True),
        sa.Column("location_state", sa.String(50), nullable=True),
        sa.Column("pain_point", sa.Text(), nullable=True),
        sa.Column("identified_service", sa.String(255), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column("media_urls", sa.JSON(), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("drop_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("re_engagement_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "re_engagement_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("business_id", "external_id", "channel", name="uq_lead_external"),
    )
    op.create_index("ix_lead_business_status", "leads", ["business_id", "status"])
    op.create_index("ix_lead_business_created", "leads", ["business_id", "created_at"])

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.Uuid(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("current_node", sa.String(100), nullable=True),
        sa.Column("graph_state", sa.JSON(), nullable=True),
        sa.Column("langgraph_thread_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("media_url", sa.String(2048), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- appointments ---
    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lead_id",
            sa.Uuid(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "duration_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")
        ),
        sa.Column("service_name", sa.String(255), nullable=True),
        sa.Column("google_event_id", sa.String(255), nullable=True),
        sa.Column("google_event_link", sa.String(2048), nullable=True),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="scheduled"
        ),
        sa.Column(
            "reminder_24h_sent", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "reminder_1h_sent", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_1h_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Uuid(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("appointments")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_lead_business_created", table_name="leads")
    op.drop_index("ix_lead_business_status", table_name="leads")
    op.drop_table("leads")
    op.drop_table("businesses")
    op.drop_table("admins")
