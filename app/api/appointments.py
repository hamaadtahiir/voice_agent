"""Appointment management routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.lead import Lead
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)

router = APIRouter()


@router.get("", response_model=dict)
async def list_appointments(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    business_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    """List appointments with filters and pagination."""
    query = select(Appointment).options(selectinload(Appointment.lead)).order_by(Appointment.scheduled_at.desc())
    count_query = select(func.count(Appointment.id))

    if business_id:
        query = query.where(Appointment.business_id == business_id)
        count_query = count_query.where(Appointment.business_id == business_id)
    if status:
        query = query.where(Appointment.status == status)
        count_query = count_query.where(Appointment.status == status)
    if date_from:
        query = query.where(Appointment.scheduled_at >= date_from)
        count_query = count_query.where(Appointment.scheduled_at >= date_from)
    if date_to:
        query = query.where(Appointment.scheduled_at <= date_to)
        count_query = count_query.where(Appointment.scheduled_at <= date_to)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    appointments = result.scalars().all()

    items = []
    for a in appointments:
        data = AppointmentResponse.model_validate(a)
        if a.lead:
            data.lead_name = a.lead.name
        items.append(data)

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    body: AppointmentCreate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually create an appointment."""
    # Validate business exists
    biz_result = await db.execute(
        select(Business).where(Business.id == body.business_id)
    )
    business = biz_result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Validate lead exists
    lead_result = await db.execute(select(Lead).where(Lead.id == body.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Verify lead belongs to business
    if lead.business_id != body.business_id:
        raise HTTPException(
            status_code=422, detail="Lead does not belong to this business"
        )

    appointment = Appointment(
        id=uuid.uuid4(),
        business_id=body.business_id,
        lead_id=body.lead_id,
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
        service_name=body.service_name,
        notes=body.notes,
        status="scheduled",
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get appointment detail."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return AppointmentResponse.model_validate(appointment)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentUpdate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update appointment status (cancel, complete, no_show)."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    update_data = body.model_dump(exclude_unset=True)

    if "status" in update_data:
        valid_statuses = {
            "scheduled",
            "confirmed",
            "reminded",
            "completed",
            "cancelled",
            "no_show",
        }
        if update_data["status"] not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        # Set cancelled_at timestamp when cancelling
        if update_data["status"] == "cancelled" and not appointment.cancelled_at:
            appointment.cancelled_at = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(appointment, field, value)

    await db.flush()
    await db.refresh(appointment)
    return AppointmentResponse.model_validate(appointment)
