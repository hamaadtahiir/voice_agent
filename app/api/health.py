"""Health check and utility endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "healthy", "service": "inbound-bot"}


@router.post("/seed")
async def seed_database(
    secret: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """One-time seed endpoint. Requires ?secret= matching ADMIN_JWT_SECRET."""
    from app.config import get_settings
    from app.models.admin import Admin
    from app.models.business import Business
    from passlib.context import CryptContext

    settings = get_settings()
    if secret != settings.ADMIN_JWT_SECRET:
        return {"error": "Invalid secret"}

    # Check if already seeded
    result = await db.execute(select(Admin).where(Admin.email == "admin@inbound-bot.com"))
    if result.scalar_one_or_none():
        return {"status": "already seeded"}

    pwd_context = CryptContext(schemes=["bcrypt"])

    admin = Admin(
        id=uuid.uuid4(),
        email="admin@inbound-bot.com",
        hashed_password=pwd_context.hash("admin123"),
        name="Super Admin",
        role="super_admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(admin)

    business = Business(
        id=uuid.uuid4(),
        name="Apex Roofing Co",
        slug="apex-roofing",
        industry="roofing",
        phone="+15551234567",
        email="info@apexroofing.com",
        website="https://apexroofing.com",
        timezone="America/New_York",
        service_areas=["10001", "10002", "10003", "10004", "10005", "11201", "11211", "07001", "07002", "07003"],
        business_hours={
            "monday": {"open": "08:00", "close": "17:00"},
            "tuesday": {"open": "08:00", "close": "17:00"},
            "wednesday": {"open": "08:00", "close": "17:00"},
            "thursday": {"open": "08:00", "close": "17:00"},
            "friday": {"open": "08:00", "close": "16:00"},
            "saturday": {"open": "09:00", "close": "13:00"},
            "sunday": {"open": "00:00", "close": "00:00", "is_closed": True},
        },
        services=[
            {"name": "Roof Inspection", "duration_min": 60, "price_min": 0, "price_max": 0, "quotable": False},
            {"name": "Roof Repair", "duration_min": 120, "price_min": 300, "price_max": 2500, "quotable": True},
            {"name": "Roof Replacement", "duration_min": 90, "price_min": 5000, "price_max": 25000, "quotable": True},
            {"name": "Gutter Cleaning", "duration_min": 60, "price_min": 100, "price_max": 400, "quotable": True},
            {"name": "Emergency Leak Repair", "duration_min": 60, "price_min": 200, "price_max": 1500, "quotable": True},
        ],
        branding={
            "primary_color": "#1e40af",
            "logo_url": None,
            "welcome_message": "Welcome to Apex Roofing! How can we help you with your roofing needs today?"
        },
        notification_emails=["info@apexroofing.com"],
        appointment_duration_default=60,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(business)

    business2 = Business(
        id=uuid.uuid4(),
        name="Green Valley Landscaping",
        slug="green-valley",
        industry="landscaping",
        phone="+15559876543",
        email="hello@greenvalley.com",
        timezone="America/Chicago",
        service_areas=["60601", "60602", "60603", "60604", "60605", "60606", "60607", "60608"],
        business_hours={
            "monday": {"open": "07:00", "close": "18:00"},
            "tuesday": {"open": "07:00", "close": "18:00"},
            "wednesday": {"open": "07:00", "close": "18:00"},
            "thursday": {"open": "07:00", "close": "18:00"},
            "friday": {"open": "07:00", "close": "17:00"},
            "saturday": {"open": "08:00", "close": "14:00"},
            "sunday": {"open": "00:00", "close": "00:00", "is_closed": True},
        },
        services=[
            {"name": "Lawn Mowing", "duration_min": 60, "price_min": 40, "price_max": 120, "quotable": True},
            {"name": "Landscape Design", "duration_min": 90, "price_min": 500, "price_max": 5000, "quotable": False},
            {"name": "Tree Trimming", "duration_min": 120, "price_min": 150, "price_max": 1500, "quotable": True},
            {"name": "Sprinkler Installation", "duration_min": 180, "price_min": 1500, "price_max": 4000, "quotable": True},
        ],
        branding={
            "primary_color": "#15803d",
            "logo_url": None,
            "welcome_message": "Hi there! Welcome to Green Valley Landscaping. How can we help transform your outdoor space?"
        },
        notification_emails=["hello@greenvalley.com"],
        appointment_duration_default=90,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(business2)

    await db.flush()
    return {
        "status": "seeded",
        "admin": "admin@inbound-bot.com / admin123",
        "businesses": ["apex-roofing", "green-valley"],
    }
