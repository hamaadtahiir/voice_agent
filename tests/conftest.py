"""Shared pytest fixtures for the Inbound Bot test suite."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base

# Import all models so that Base.metadata is fully populated before
# create_all / drop_all runs.
import app.models  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_inbound_bot.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """Create and tear down the test database engine (session scope)."""
    eng = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db(engine):
    """Provide a transactional database session that rolls back after each test."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_business(db: AsyncSession):
    """Insert and return a sample roofing business for testing."""
    from app.models.business import Business

    business = Business(
        id=uuid.uuid4(),
        name="Test Roofing Co",
        slug="test-roofing",
        industry="roofing",
        timezone="America/New_York",
        service_areas=["10001", "10002", "10003"],
        business_hours={
            "monday": {"open": "09:00", "close": "17:00"},
            "tuesday": {"open": "09:00", "close": "17:00"},
            "wednesday": {"open": "09:00", "close": "17:00"},
            "thursday": {"open": "09:00", "close": "17:00"},
            "friday": {"open": "09:00", "close": "17:00"},
        },
        services=[
            {
                "name": "Roof Inspection",
                "duration_min": 60,
                "price_min": 0,
                "price_max": 0,
                "quotable": False,
            },
            {
                "name": "Roof Repair",
                "duration_min": 120,
                "price_min": 300,
                "price_max": 2500,
                "quotable": True,
            },
        ],
        branding={
            "primary_color": "#1e40af",
            "welcome_message": "Welcome! How can we help?",
        },
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


@pytest.fixture
async def sample_lead(db: AsyncSession, sample_business):
    """Insert and return a sample lead linked to the sample business."""
    from app.models.lead import Lead

    lead = Lead(
        id=uuid.uuid4(),
        business_id=sample_business.id,
        channel="web_chat",
        name="John Doe",
        phone="+15551234567",
        email="john@example.com",
        location_zip="10001",
        status="qualifying",
        created_at=datetime.now(timezone.utc),
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead
