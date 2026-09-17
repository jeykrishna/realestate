from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.property import Property, PropertyStatus, PropertyCategory
from app.schemas.city import CityOut, CitiesResponse, PropertyCounts
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("", response_model=CitiesResponse, response_model_by_alias=True)
def list_cities(db: Session = Depends(get_db)):
    rows = (
        db.query(Property.city, Property.category, func.count(Property.id).label("cnt"))
        .filter(Property.status == PropertyStatus.active)
        .group_by(Property.city, Property.category)
        .all()
    )

    city_map: dict[str, dict] = {}
    for city, category, cnt in rows:
        if city not in city_map:
            city_map[city] = {"residential": 0, "agriculture": 0, "commercial": 0}
        city_map[city][category.value] = cnt

    cities = []
    for city, counts in sorted(city_map.items()):
        total = sum(counts.values())
        cities.append(CityOut(
            slug=city.lower().replace(" ", "-"),
            name=city,
            state="Tamil Nadu",
            image=f"{settings.CDN_BASE_URL}/cities/{city.lower()}.jpg",
            property_count=total,
            property_counts=PropertyCounts(
                residential=counts.get("residential", 0),
                agriculture=counts.get("agriculture", 0),
                commercial=counts.get("commercial", 0),
                total=total,
            ),
        ))

    return CitiesResponse(cities=cities)
