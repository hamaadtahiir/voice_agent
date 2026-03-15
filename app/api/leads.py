"""Lead management routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.schemas.conversation import ConversationResponse
from app.schemas.lead import LeadResponse, LeadUpdate

router = APIRouter()


@router.get("", response_model=dict)
async def list_leads(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    business_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    """List leads with filters and pagination."""
    query = select(Lead).order_by(Lead.created_at.desc())
    count_query = select(func.count(Lead.id))

    # Apply filters
    if business_id:
        query = query.where(Lead.business_id == business_id)
        count_query = count_query.where(Lead.business_id == business_id)
    if status:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)
    if channel:
        query = query.where(Lead.channel == channel)
        count_query = count_query.where(Lead.channel == channel)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    leads = result.scalars().all()

    return {
        "items": [LeadResponse.model_validate(lead) for lead in leads],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a single lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update lead status or score."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = body.model_dump(exclude_unset=True)

    # Validate status if provided
    if "status" in update_data:
        valid_statuses = {
            "new",
            "qualifying",
            "qualified",
            "appointment_booked",
            "appointment_completed",
            "lost",
            "out_of_area",
        }
        if update_data["status"] not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

    for field, value in update_data.items():
        # LeadUpdate has a 'notes' field but Lead does not; skip it
        if hasattr(lead, field):
            setattr(lead, field, value)

    await db.flush()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}/conversations", response_model=list[ConversationResponse])
async def get_lead_conversations(
    lead_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get all conversations for a lead, including messages."""
    # Verify lead exists
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.lead_id == lead_id)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.started_at.desc())
    )
    conversations = result.scalars().all()
    return [ConversationResponse.model_validate(c) for c in conversations]
