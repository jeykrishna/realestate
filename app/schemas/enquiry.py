from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.enquiry import EnquiryStatus


class EnquiryCreate(BaseModel):
    """Frontend sends camelCase; both camelCase and snake_case are accepted."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    email: EmailStr
    phone: str
    city: Optional[str] = None
    message: Optional[str] = None
    property_id: str = Field(validation_alias="propertyId")
    plot_id: Optional[str] = Field(default=None, validation_alias="plotId")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 10:
            raise ValueError("Phone must be exactly 10 digits")
        return v


class EnquiryOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    email: str
    phone: str
    city: Optional[str] = None
    message: Optional[str] = None
    property_id: str = Field(serialization_alias="propertyId")
    property_name: Optional[str] = Field(default=None, serialization_alias="propertyName")
    plot_id: Optional[str] = Field(default=None, serialization_alias="plotId")
    plot_number: Optional[str] = Field(default=None, serialization_alias="plotNumber")
    status: str
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")


class EnquiryCreateResponse(BaseModel):
    """POST /enquiries response matching the doc."""
    success: bool = True
    enquiry_id: str = Field(serialization_alias="enquiryId")
    message: str = "Your enquiry has been submitted successfully."

    model_config = ConfigDict(populate_by_name=True)


class Pagination(BaseModel):
    page: int
    limit: int
    total: int

    model_config = ConfigDict(populate_by_name=True)


class EnquiryListResponse(BaseModel):
    """GET /enquiries response — {data, pagination} as per doc."""
    data: list[EnquiryOut]
    pagination: Pagination

    model_config = ConfigDict(populate_by_name=True)


class EnquiryStatusUpdate(BaseModel):
    status: EnquiryStatus


class EnquiryUpdateResponse(BaseModel):
    """PATCH /enquiries/:id/status response."""
    success: bool = True
    id: str
    status: str

    model_config = ConfigDict(populate_by_name=True)
