from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class PropertyCounts(BaseModel):
    residential: int = 0
    agriculture: int = 0
    commercial: int = 0
    total: int = 0


class CityOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    name: str
    state: str = "Tamil Nadu"
    image: Optional[str] = None
    property_count: int = Field(default=0, serialization_alias="propertyCount")
    # Detailed breakdown kept for admin consumers
    property_counts: PropertyCounts = Field(
        default_factory=PropertyCounts, serialization_alias="propertyCounts"
    )


class CitiesResponse(BaseModel):
    cities: list[CityOut]
