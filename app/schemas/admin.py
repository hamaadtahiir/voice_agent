import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminLogin(BaseModel):
    email: str
    password: str


class AdminCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = "support"


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
