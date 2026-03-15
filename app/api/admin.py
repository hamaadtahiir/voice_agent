"""Admin authentication and management routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import create_access_token, get_current_admin, require_super_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.schemas.admin import AdminCreate, AdminLogin, AdminResponse, TokenResponse

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=TokenResponse)
async def login(
    body: AdminLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate admin and return JWT token."""
    result = await db.execute(select(Admin).where(Admin.email == body.email))
    admin = result.scalar_one_or_none()

    if not admin or not pwd_context.verify(body.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token(str(admin.id))
    return TokenResponse(access_token=token)


@router.post("/register", response_model=AdminResponse, status_code=201)
async def register_admin(
    body: AdminCreate,
    admin: Admin = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new admin account (super_admin only)."""
    # Check for duplicate email
    existing = await db.execute(select(Admin).where(Admin.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate role
    valid_roles = {"super_admin", "admin", "support"}
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    new_admin = Admin(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
        name=body.name,
        role=body.role,
        is_active=True,
    )
    db.add(new_admin)
    await db.flush()
    await db.refresh(new_admin)
    return AdminResponse.model_validate(new_admin)


@router.get("/me", response_model=AdminResponse)
async def get_me(
    admin: Admin = Depends(get_current_admin),
):
    """Return the currently authenticated admin."""
    return AdminResponse.model_validate(admin)


@router.get("/list", response_model=list[AdminResponse])
async def list_admins(
    admin: Admin = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all admin accounts (super_admin only)."""
    result = await db.execute(
        select(Admin).order_by(Admin.created_at.desc())
    )
    admins = result.scalars().all()
    return [AdminResponse.model_validate(a) for a in admins]
