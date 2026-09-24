from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator, field_validator
from typing import Optional, Literal
import re


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., description="10-digit mobile number")
    role: Literal["admin", "owner", "super_admin"] = "owner"
    property_ids: list[str] = Field(default=[], description="Property IDs assigned to this owner")
    secret_key: Optional[str] = Field(
        default=None, description="Required when role is 'admin' or 'super_admin'"
    )
    password: Optional[str] = Field(
        default=None, min_length=8, description="Required when role is 'admin' or 'super_admin'"
    )
    otp: Optional[str] = Field(
        default=None,
        description="Email verification code from POST /auth/register/send-otp — required when role is 'admin' or 'super_admin'",
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) != 10:
            raise ValueError("Phone must be a 10-digit Indian mobile number")
        return digits


class RegisterResponse(BaseModel):
    success: bool = True
    message: str
    user: "UserOut"


class RegisterSendOtpRequest(BaseModel):
    email: EmailStr


# ── OTP ───────────────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    """Accept either email OR phone (not both required)."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None  # E.164 format e.g. +919876543210

    @model_validator(mode="after")
    def check_email_or_phone(self) -> "SendOTPRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class SendOTPResponse(BaseModel):
    success: bool
    message: str


class VerifyOTPRequest(BaseModel):
    """Accept either email OR phone to verify OTP."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    otp: str

    @model_validator(mode="after")
    def check_email_or_phone(self) -> "VerifyOTPRequest":
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str
    email: str
    phone: str
    role: str
    property_ids: list[str] = Field(default=[], serialization_alias="propertyIds")


class VerifyOTPResponse(BaseModel):
    """Token delivered via HttpOnly cookie AND response body for cross-origin clients."""
    success: bool = True
    user: UserOut
    token: Optional[str] = None   # JWT token for localStorage (S3/cross-origin clients)

    model_config = ConfigDict(populate_by_name=True)


# ── Password login (admin / super admin) ────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Same shape as VerifyOTPResponse — password login is a drop-in replacement
    for OTP login on the admin side."""
    success: bool = True
    user: UserOut
    token: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class LogoutResponse(BaseModel):
    success: bool


# Resolve forward reference
RegisterResponse.model_rebuild()
