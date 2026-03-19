"""Business CRUD routes."""

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import get_settings
from app.db.session import get_db
from app.models.admin import Admin
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate
from app.services.calendar_service import handle_oauth_callback, initiate_oauth

router = APIRouter()


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a business name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@router.get("", response_model=list[BusinessResponse])
async def list_businesses(
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    is_active: Optional[bool] = Query(None),
):
    """List all businesses."""
    query = select(Business).order_by(Business.created_at.desc())
    if is_active is not None:
        query = query.where(Business.is_active == is_active)
    result = await db.execute(query)
    businesses = result.scalars().all()
    return [BusinessResponse.model_validate(b) for b in businesses]


@router.post("", response_model=BusinessResponse, status_code=201)
async def create_business(
    body: BusinessCreate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new business."""
    # Auto-generate slug if empty
    slug = body.slug.strip() if body.slug else _slugify(body.name)
    if not slug:
        slug = _slugify(body.name)

    # Ensure slug uniqueness
    existing = await db.execute(select(Business).where(Business.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A business with this slug already exists")

    business = Business(
        id=uuid.uuid4(),
        name=body.name,
        slug=slug,
        industry=body.industry,
        phone=body.phone,
        email=body.email,
        website=body.website,
        timezone=body.timezone,
        service_areas=body.service_areas,
        business_hours=body.business_hours,
        services=body.services,
        branding=body.branding,
        appointment_duration_default=body.appointment_duration_default,
        is_active=True,
    )
    db.add(business)
    await db.flush()
    await db.refresh(business)
    return BusinessResponse.model_validate(business)


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback and store tokens on business."""
    # state is the business_id
    business_id = state

    try:
        await handle_oauth_callback(code=code, business_id=business_id, db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OAuth callback failed: {str(exc)}",
        )

    settings = get_settings()
    return RedirectResponse(
        url=f"{settings.BASE_URL}/admin/businesses/{business_id}?oauth=success"
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a business by ID."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse.model_validate(business)


@router.put("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: uuid.UUID,
    body: BusinessUpdate,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a business."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = body.model_dump(exclude_unset=True)

    # Check slug uniqueness if being changed
    if "slug" in update_data and update_data["slug"] != business.slug:
        existing = await db.execute(
            select(Business).where(
                Business.slug == update_data["slug"],
                Business.id != business_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="A business with this slug already exists"
            )

    for field, value in update_data.items():
        setattr(business, field, value)

    await db.flush()
    await db.refresh(business)

    # Sync assistant config to Vapi if the business has a Vapi assistant
    if business.vapi_assistant_id:
        from app.api.vapi import sync_vapi_assistant
        await sync_vapi_assistant(business)

    return BusinessResponse.model_validate(business)


@router.delete("/{business_id}")
async def delete_business(
    business_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a business by setting is_active to False."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    business.is_active = False
    await db.flush()
    return {"detail": "Business deactivated"}


@router.get("/{business_id}/oauth/google")
async def initiate_google_oauth(
    business_id: uuid.UUID,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Initiate Google OAuth flow for a business."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    try:
        auth_url = initiate_oauth(business_id=str(business.id))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to initiate OAuth: {str(exc)}",
        )

    return RedirectResponse(url=auth_url)
