"""Shared dependencies for API routes."""

import uuid as uuid_mod
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.admin import Admin

security = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """Validate JWT token and return current admin."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.ADMIN_JWT_SECRET,
            algorithms=[settings.ADMIN_JWT_ALGORITHM],
        )
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        admin_uuid = uuid_mod.UUID(admin_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(Admin).where(Admin.id == admin_uuid))
    admin = result.scalar_one_or_none()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin not found or inactive")
    return admin


async def require_super_admin(
    admin: Admin = Depends(get_current_admin),
) -> Admin:
    """Require the current admin to have the super_admin role."""
    if admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin required")
    return admin


def create_access_token(admin_id: str) -> str:
    """Create JWT token for admin."""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.ADMIN_JWT_EXPIRE_MINUTES)
    payload = {"sub": str(admin_id), "exp": expire}
    return jwt.encode(
        payload, settings.ADMIN_JWT_SECRET, algorithm=settings.ADMIN_JWT_ALGORITHM
    )
