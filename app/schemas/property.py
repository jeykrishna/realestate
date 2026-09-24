from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Any
from datetime import datetime
from app.models.property import PropertyCategory, PropertyStatus


# ── Nested helpers ────────────────────────────────────────────────────────────

class LocationSchema(BaseModel):
    lat: float
    lng: float


class PriceRange(BaseModel):
    min: int
    max: int


class SqftRange(BaseModel):
    min: int
    max: int


class PlotsCount(BaseModel):
    total: int
    available: int
    booked: int
    reserved: int


class Pagination(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


# ── Create / Update ───────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    """What the frontend POSTs to create a property.
    All camelCase aliases are accepted; owner_id and slug are derived server-side.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    city: str
    category: PropertyCategory

    # Location — accept flat lat/lng OR nested object
    lat: Optional[float] = None
    lng: Optional[float] = None
    location: Optional[LocationSchema] = None

    video_url: Optional[str] = Field(default=None, validation_alias="videoUrl")
    map_embed_url: Optional[str] = Field(default=None, validation_alias="mapEmbedUrl")
    rera_number: Optional[str] = Field(default=None, validation_alias="reraNumber")
    status: PropertyStatus = PropertyStatus.draft
    amenities: list[str] = []

    # Property metadata fields
    plot_area_sqft: Optional[int] = Field(default=None, validation_alias="plotAreaSqft")
    dimensions: Optional[str] = None          # "25 X 40"
    boundary_wall: Optional[bool] = Field(default=None, validation_alias="boundaryWall")
    ownership_type: Optional[str] = Field(default=None, validation_alias="ownershipType")
    overlooking: list[str] = []
    transaction_type: Optional[str] = Field(default=None, validation_alias="transactionType")
    construction_done: Optional[bool] = Field(default=None, validation_alias="constructionDone")
    facing: Optional[str] = None
    gated_community: Optional[bool] = Field(default=None, validation_alias="gatedCommunity")
    corner_plot: Optional[bool] = Field(default=None, validation_alias="cornerPlot")
    price_per_sqft: Optional[int] = Field(default=None, validation_alias="pricePerSqft")
    starting_price: Optional[int] = Field(default=None, validation_alias="startingPrice")

    @model_validator(mode="after")
    def resolve_location(self) -> "PropertyCreate":
        """Merge flat lat/lng into location if location not provided."""
        if self.location is None and self.lat is not None and self.lng is not None:
            self.location = LocationSchema(lat=self.lat, lng=self.lng)
        return self


class PropertyUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    category: Optional[PropertyCategory] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    location: Optional[LocationSchema] = None
    video_url: Optional[str] = Field(default=None, validation_alias="videoUrl")
    map_embed_url: Optional[str] = Field(default=None, validation_alias="mapEmbedUrl")
    rera_number: Optional[str] = Field(default=None, validation_alias="reraNumber")
    status: Optional[PropertyStatus] = None
    amenities: Optional[list[str]] = None
    owner_id: Optional[str] = Field(default=None, validation_alias="ownerId")

    plot_area_sqft: Optional[int] = Field(default=None, validation_alias="plotAreaSqft")
    dimensions: Optional[str] = None
    boundary_wall: Optional[bool] = Field(default=None, validation_alias="boundaryWall")
    ownership_type: Optional[str] = Field(default=None, validation_alias="ownershipType")
    overlooking: Optional[list[str]] = None
    transaction_type: Optional[str] = Field(default=None, validation_alias="transactionType")
    construction_done: Optional[bool] = Field(default=None, validation_alias="constructionDone")
    facing: Optional[str] = None
    gated_community: Optional[bool] = Field(default=None, validation_alias="gatedCommunity")
    corner_plot: Optional[bool] = Field(default=None, validation_alias="cornerPlot")
    price_per_sqft: Optional[int] = Field(default=None, validation_alias="pricePerSqft")
    starting_price: Optional[int] = Field(default=None, validation_alias="startingPrice")

    hero_image: Optional[str] = Field(default=None, validation_alias="heroImage")
    images: Optional[list[str]] = None

    @model_validator(mode="after")
    def resolve_location(self) -> "PropertyUpdate":
        if self.location is None and self.lat is not None and self.lng is not None:
            self.location = LocationSchema(lat=self.lat, lng=self.lng)
        return self


# ── Output ────────────────────────────────────────────────────────────────────

class PropertyOut(BaseModel):
    """Response shape — serialized with camelCase aliases (by_alias=True on routes)."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    owner_id: str = Field(serialization_alias="ownerId")
    name: str
    slug: str
    description: str
    city: str
    category: str
    status: str

    # Location — flat output
    lat: Optional[float] = None
    lng: Optional[float] = None

    # Plot statistics
    total_plots: int = Field(default=0, serialization_alias="totalPlots")
    available_plots: int = Field(default=0, serialization_alias="availablePlots")
    views_count: int = Field(default=0, serialization_alias="viewsCount")
    starting_price: Optional[int] = Field(default=None, serialization_alias="startingPrice")

    # Media
    hero_image: Optional[str] = Field(default=None, serialization_alias="heroImage")
    images: list[str] = []                          # gallery / images
    video_url: Optional[str] = Field(default=None, serialization_alias="videoUrl")
    map_embed_url: Optional[str] = Field(default=None, serialization_alias="mapEmbedUrl")

    # Legal
    rera_number: Optional[str] = Field(default=None, serialization_alias="reraNumber")
    amenities: list[str] = []

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt")

    # Property metadata
    plot_area_sqft: Optional[int] = Field(default=None, serialization_alias="plotAreaSqft")
    dimensions: Optional[str] = None               # "25 X 40"
    boundary_wall: Optional[bool] = Field(default=None, serialization_alias="boundaryWall")
    ownership_type: Optional[str] = Field(default=None, serialization_alias="ownershipType")
    overlooking: list[str] = []
    transaction_type: Optional[str] = Field(default=None, serialization_alias="transactionType")
    construction_done: Optional[bool] = Field(default=None, serialization_alias="constructionDone")
    facing: Optional[str] = None
    gated_community: Optional[bool] = Field(default=None, serialization_alias="gatedCommunity")
    corner_plot: Optional[bool] = Field(default=None, serialization_alias="cornerPlot")
    price_per_sqft: Optional[int] = Field(default=None, serialization_alias="pricePerSqft")

    # Owner contact (fetched from users table)
    owner_phone: Optional[str] = Field(default=None, serialization_alias="ownerPhone")

    # Approval workflow
    approval_status: str = Field(default="approved", serialization_alias="approvalStatus")
    approved_by: Optional[str] = Field(default=None, serialization_alias="approvedBy")
    approved_at: Optional[datetime] = Field(default=None, serialization_alias="approvedAt")
    rejection_reason: Optional[str] = Field(default=None, serialization_alias="rejectionReason")


class PropertyRejectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    reason: Optional[str] = None


class PropertyCreateResponse(BaseModel):
    """Slim response returned after POST /properties."""
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    property: dict   # {id, slug, ownerId, createdAt, viewsCount, totalPlots, availablePlots}


class PropertyListResponse(BaseModel):
    """List response with pagination — matches {data, pagination} doc shape."""
    model_config = ConfigDict(populate_by_name=True)

    data: list[PropertyOut]
    pagination: Pagination


class PropertyDeleteResponse(BaseModel):
    success: bool
