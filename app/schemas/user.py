from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    role: UserRole = UserRole.owner
    property_ids: list[str] = []

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 10:
            raise ValueError("Phone must be exactly 10 digits")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    property_ids: Optional[list[str]] = None


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    role: str
    property_ids: list[str] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserOut]


class UserCreateResponse(BaseModel):
    user: UserOut


class UserDeleteResponse(BaseModel):
    success: bool
