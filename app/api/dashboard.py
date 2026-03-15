"""Dashboard analytics API."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.appointment import Appointment
from app.models.lead import Lead

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    business_id: Optional[uuid.UUID] = Query(None),
):
    """Return dashboard analytics for a business or across all businesses."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Base filter conditions
    lead_filters = []
    appt_filters = []
    if business_id:
        lead_filters.append(Lead.business_id == business_id)
        appt_filters.append(Appointment.business_id == business_id)

    # 1. Leads this week
    leads_week_query = select(func.count(Lead.id)).where(
        Lead.created_at >= week_ago,
        *lead_filters,
    )
    leads_week_result = await db.execute(leads_week_query)
    leads_this_week = leads_week_result.scalar() or 0

    # 2. Total leads
    total_leads_query = select(func.count(Lead.id)).where(*lead_filters)
    total_leads_result = await db.execute(total_leads_query)
    total_leads = total_leads_result.scalar() or 0

    # 3. Leads by channel
    channel_query = (
        select(Lead.channel, func.count(Lead.id).label("count"))
        .where(*lead_filters)
        .group_by(Lead.channel)
    )
    channel_result = await db.execute(channel_query)
    leads_by_channel = {row.channel: row.count for row in channel_result.all()}

    # 4. Leads by status
    status_query = (
        select(Lead.status, func.count(Lead.id).label("count"))
        .where(*lead_filters)
        .group_by(Lead.status)
    )
    status_result = await db.execute(status_query)
    leads_by_status = {row.status: row.count for row in status_result.all()}

    # 5. Conversion rate (leads that reached appointment_booked or appointment_completed)
    converted_statuses = {"appointment_booked", "appointment_completed"}
    converted_count = sum(
        count for status, count in leads_by_status.items()
        if status in converted_statuses
    )
    conversion_rate = (
        round((converted_count / total_leads) * 100, 1) if total_leads > 0 else 0.0
    )

    # 6. Upcoming appointments (scheduled, confirmed, reminded)
    upcoming_query = select(func.count(Appointment.id)).where(
        Appointment.scheduled_at >= now,
        Appointment.status.in_(["scheduled", "confirmed", "reminded"]),
        *appt_filters,
    )
    upcoming_result = await db.execute(upcoming_query)
    upcoming_appointments_count = upcoming_result.scalar() or 0

    # 7. Appointments this week
    appts_week_query = select(func.count(Appointment.id)).where(
        Appointment.scheduled_at >= week_ago,
        Appointment.scheduled_at <= now + timedelta(days=7),
        *appt_filters,
    )
    appts_week_result = await db.execute(appts_week_query)
    appointments_this_week = appts_week_result.scalar() or 0

    # 8. Average lead score
    avg_score_query = select(func.avg(Lead.score)).where(
        Lead.score.isnot(None),
        Lead.score > 0,
        *lead_filters,
    )
    avg_score_result = await db.execute(avg_score_query)
    avg_score_raw = avg_score_result.scalar()
    average_lead_score = round(float(avg_score_raw), 1) if avg_score_raw else 0.0

    return {
        "leads_this_week": leads_this_week,
        "total_leads": total_leads,
        "leads_by_channel": leads_by_channel,
        "leads_by_status": leads_by_status,
        "conversion_rate": conversion_rate,
        "upcoming_appointments_count": upcoming_appointments_count,
        "appointments_this_week": appointments_this_week,
        "average_lead_score": average_lead_score,
    }
