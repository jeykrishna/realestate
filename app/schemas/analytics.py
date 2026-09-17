from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.analytics import EventType


# ── Track Event ───────────────────────────────────────────────────────────────

class TrackEventRequest(BaseModel):
    """Accepts both camelCase (frontend) and snake_case."""
    model_config = ConfigDict(populate_by_name=True)

    event_type: EventType = Field(validation_alias="eventType")
    property_id: str = Field(validation_alias="propertyId")
    plot_id: Optional[str] = Field(default=None, validation_alias="plotId")
    session_id: Optional[str] = Field(default=None, validation_alias="sessionId")
    timestamp: Optional[datetime] = None


class TrackEventResponse(BaseModel):
    success: bool


# ── Analytics Summary ─────────────────────────────────────────────────────────

class PropertyAnalytics(BaseModel):
    """Per-property breakdown — returned in byProperty array."""
    model_config = ConfigDict(populate_by_name=True)

    property_id: str = Field(serialization_alias="propertyId")
    property_name: str = Field(serialization_alias="propertyName")
    views: int
    phone_clicks: int = Field(default=0, serialization_alias="phoneClicks")
    whatsapp_clicks: int = Field(default=0, serialization_alias="whatsappClicks")
    enquiries: int = 0


class DailyViewEntry(BaseModel):
    date: str
    count: int


class CategoryEntry(BaseModel):
    category: str
    count: int


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_views: int = Field(serialization_alias="totalViews")
    phone_clicks: int = Field(serialization_alias="phoneClicks")
    whatsapp_clicks: int = Field(serialization_alias="whatsappClicks")
    enquiries: int                              # total enquiry_submit events


class AnalyticsSummaryResponse(BaseModel):
    """Top-level GET /analytics response."""
    model_config = ConfigDict(populate_by_name=True)

    summary: AnalyticsSummary
    by_property: list[PropertyAnalytics] = Field(default=[], serialization_alias="byProperty")
    views_over_time: list[DailyViewEntry] = Field(default=[], serialization_alias="viewsOverTime")
    category_breakdown: list[CategoryEntry] = Field(default=[], serialization_alias="categoryBreakdown")
