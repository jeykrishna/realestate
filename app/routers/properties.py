from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timezone
import math

from app.database import get_db
from app.models.property import Property, PropertyStatus, ApprovalStatus
from app.models.plot import Plot, PlotStatus
from app.models.user import User, UserRole
from app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyOut,
    PropertyListResponse, PropertyDeleteResponse, PropertyCreateResponse,
    PropertyRejectRequest, Pagination,
)
from app.dependencies.auth import require_admin, require_super_admin, get_optional_current_user
from app.utils.id_gen import make_id
from app.utils.slug import make_slug

router = APIRouter(prefix="/properties", tags=["Properties"])


def _property_to_out(prop: Property, db: Session) -> PropertyOut:
    plots = db.query(Plot).filter(Plot.property_id == prop.id).all()
    total_plots = len(plots)
    available_plots = sum(1 for p in plots if p.status == PlotStatus.available)

    # Fetch owner phone from users table
    owner = db.query(User).filter(User.id == prop.owner_id).first()
    owner_phone = owner.phone if owner else None

    # Flatten location
    lat = lng = None
    if prop.location:
        loc = prop.location if isinstance(prop.location, dict) else {}
        lat = loc.get("lat")
        lng = loc.get("lng")

    # Starting price: explicit column first, then derive from price_range
    starting_price = prop.starting_price
    if starting_price is None and prop.price_range:
        pr = prop.price_range if isinstance(prop.price_range, dict) else {}
        starting_price = pr.get("min")

    return PropertyOut(
        id=prop.id,
        owner_id=prop.owner_id,
        name=prop.name,
        slug=prop.slug,
        description=prop.description,
        city=prop.city,
        category=prop.category.value,
        status=prop.status.value,
        lat=lat,
        lng=lng,
        total_plots=total_plots,
        available_plots=available_plots,
        views_count=prop.views_count or 0,
        starting_price=starting_price,
        hero_image=prop.hero_image,
        images=prop.gallery or [],
        video_url=prop.video_url,
        map_embed_url=prop.map_embed_url,
        rera_number=prop.rera_number,
        amenities=prop.amenities or [],
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        plot_area_sqft=prop.plot_area_sqft,
        dimensions=prop.dimensions_label,
        boundary_wall=prop.boundary_wall,
        ownership_type=prop.ownership_type,
        overlooking=prop.overlooking or [],
        transaction_type=prop.transaction_type,
        construction_done=prop.construction_done,
        facing=prop.facing,
        gated_community=prop.gated_community,
        corner_plot=prop.corner_plot,
        price_per_sqft=prop.price_per_sqft,
        owner_phone=owner_phone,
        approval_status=prop.approval_status.value,
        approved_by=prop.approved_by,
        approved_at=prop.approved_at,
        rejection_reason=prop.rejection_reason,
    )


def _build_paginated_response(
    props: list[Property], db: Session, total: int, page: int, limit: int
) -> PropertyListResponse:
    data = [_property_to_out(p, db) for p in props]
    total_pages = math.ceil(total / limit) if limit else 1
    return PropertyListResponse(
        data=data,
        pagination=Pagination(page=page, limit=limit, total=total, total_pages=total_pages),
    )


# ── GET /properties ───────────────────────────────────────────────────────────

@router.get("", response_model=PropertyListResponse, response_model_by_alias=True)
def list_properties(
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="active|draft|archived"),
    approval_status: Optional[str] = Query(
        None, alias="approvalStatus", description="pending|approved|rejected (staff only)"
    ),
    search: Optional[str] = Query(None, description="Search in name/description"),
    min_price: Optional[int] = Query(None, alias="minPrice"),
    max_price: Optional[int] = Query(None, alias="maxPrice"),
    facing: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    is_staff = bool(current_user and current_user.role in (UserRole.admin, UserRole.super_admin))

    q = db.query(Property)

    if is_staff:
        # Staff (admin/super admin) manage their own dashboard — show every
        # status/approval state unless they explicitly filter.
        if status:
            q = q.filter(Property.status == status)
        if approval_status:
            q = q.filter(Property.approval_status == approval_status)
        if current_user.role == UserRole.admin:
            # Regular admins only see properties they created themselves.
            # Super admins keep the full, unfiltered view.
            q = q.filter(Property.owner_id == current_user.id)
    else:
        # Public storefront never shows drafts, archived, or not-yet-approved listings.
        q = q.filter(Property.status == (status or PropertyStatus.active))
        q = q.filter(Property.approval_status == ApprovalStatus.approved)

    if city:
        q = q.filter(func.lower(Property.city) == city.lower())
    if category:
        q = q.filter(Property.category == category)
    if search:
        q = q.filter(Property.name.ilike(f"%{search}%"))
    if facing:
        q = q.filter(func.lower(Property.facing) == facing.lower())

    total = q.count()
    props = q.offset((page - 1) * limit).limit(limit).all()

    # Post-filter by price (stored in price_range JSON)
    if min_price is not None or max_price is not None:
        filtered = []
        for p in props:
            sp = p.starting_price
            if sp is None and p.price_range:
                pr = p.price_range if isinstance(p.price_range, dict) else {}
                sp = pr.get("min")
            if sp is None:
                sp = 0
            if min_price is not None and sp < min_price:
                continue
            if max_price is not None and sp > max_price:
                continue
            filtered.append(p)
        props = filtered
        total = len(filtered)

    return _build_paginated_response(props, db, total, page, limit)


# ── GET /properties/search ────────────────────────────────────────────────────

@router.get("/search", response_model=PropertyListResponse, response_model_by_alias=True)
def search_properties(
    q: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None, alias="minPrice"),
    max_price: Optional[int] = Query(None, alias="maxPrice"),
    min_sqft: Optional[int] = Query(None, alias="minSqft"),
    max_sqft: Optional[int] = Query(None, alias="maxSqft"),
    facing: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Property).filter(
        Property.status == PropertyStatus.active,
        Property.approval_status == ApprovalStatus.approved,
    )

    if city:
        query = query.filter(func.lower(Property.city) == city.lower())
    if category:
        query = query.filter(Property.category == category)
    if q:
        query = query.filter(Property.name.ilike(f"%{q}%"))
    if facing:
        query = query.filter(func.lower(Property.facing) == facing.lower())
    if min_sqft is not None:
        query = query.filter(Property.plot_area_sqft >= min_sqft)
    if max_sqft is not None:
        query = query.filter(Property.plot_area_sqft <= max_sqft)

    total = query.count()
    props = query.offset((page - 1) * limit).limit(limit).all()

    # Post-filter by price
    if min_price is not None or max_price is not None:
        filtered = []
        for p in props:
            sp = p.starting_price or (p.price_range or {}).get("min", 0)
            if min_price is not None and sp < min_price:
                continue
            if max_price is not None and sp > max_price:
                continue
            filtered.append(p)
        props = filtered
        total = len(filtered)

    return _build_paginated_response(props, db, total, page, limit)


# ── GET /properties/:slug ─────────────────────────────────────────────────────

@router.get("/{slug}", response_model=PropertyOut, response_model_by_alias=True)
def get_property(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    prop = (
        db.query(Property)
        .filter((Property.slug == slug) | (Property.id == slug))
        .first()
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    is_staff = bool(current_user and current_user.role in (UserRole.admin, UserRole.super_admin))
    is_owner = bool(current_user and current_user.id == prop.owner_id)
    if not is_staff and not is_owner and prop.approval_status != ApprovalStatus.approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    return _property_to_out(prop, db)


# ── POST /properties ──────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    slug = make_slug(payload.name)
    # Ensure slug is unique
    base_slug = slug
    counter = 1
    while db.query(Property).filter(Property.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    location_dict = payload.location.model_dump() if payload.location else None

    # Super admins publish straight through; regular admins queue for approval.
    is_super_admin = current_user.role == UserRole.super_admin
    approval_status = ApprovalStatus.approved if is_super_admin else ApprovalStatus.pending
    approved_by = current_user.id if is_super_admin else None
    approved_at = datetime.now(timezone.utc) if is_super_admin else None

    prop = Property(
        id=make_id("prop"),
        slug=slug,
        name=payload.name,
        city=payload.city,
        category=payload.category,
        description=payload.description,
        location=location_dict,
        rera_number=payload.rera_number,
        amenities=payload.amenities,
        video_url=payload.video_url,
        map_embed_url=payload.map_embed_url,
        status=payload.status,
        approval_status=approval_status,
        approved_by=approved_by,
        approved_at=approved_at,
        owner_id=current_user.id,
        plot_area_sqft=payload.plot_area_sqft,
        dimensions_label=payload.dimensions,
        boundary_wall=payload.boundary_wall,
        ownership_type=payload.ownership_type,
        overlooking=payload.overlooking or [],
        transaction_type=payload.transaction_type,
        construction_done=payload.construction_done,
        facing=payload.facing,
        gated_community=payload.gated_community,
        corner_plot=payload.corner_plot,
        price_per_sqft=payload.price_per_sqft,
        starting_price=payload.starting_price,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)

    return {
        "success": True,
        "property": {
            "id": prop.id,
            "slug": prop.slug,
            "ownerId": prop.owner_id,
            "createdAt": prop.created_at.isoformat() if prop.created_at else None,
            "viewsCount": prop.views_count or 0,
            "totalPlots": prop.total_plots or 0,
            "availablePlots": prop.available_plots or 0,
            "approvalStatus": prop.approval_status.value,
        },
    }


# ── PUT /properties/:id ───────────────────────────────────────────────────────

@router.put("/{property_id}", response_model=PropertyOut, response_model_by_alias=True)
def update_property(
    property_id: str,
    payload: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role == UserRole.admin and prop.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit properties you created")

    update_data = payload.model_dump(exclude_unset=True)

    # Resolve location
    if "location" in update_data and update_data["location"]:
        loc = update_data.pop("location")
        update_data["location"] = loc.model_dump() if hasattr(loc, "model_dump") else loc
    elif "lat" in update_data or "lng" in update_data:
        lat = update_data.pop("lat", None) or (prop.location or {}).get("lat")
        lng = update_data.pop("lng", None) or (prop.location or {}).get("lng")
        if lat and lng:
            update_data["location"] = {"lat": lat, "lng": lng}

    # Map schema field → model column
    field_map = {"dimensions": "dimensions_label", "images": "gallery"}
    for schema_field, model_col in field_map.items():
        if schema_field in update_data:
            update_data[model_col] = update_data.pop(schema_field)

    for field, value in update_data.items():
        if hasattr(prop, field):
            setattr(prop, field, value)

    db.commit()
    db.refresh(prop)
    return _property_to_out(prop, db)


# ── DELETE /properties/:id ────────────────────────────────────────────────────

@router.delete("/{property_id}", response_model=PropertyDeleteResponse)
def delete_property(
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if current_user.role == UserRole.admin and prop.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete properties you created")

    prop.status = PropertyStatus.archived
    db.commit()
    return PropertyDeleteResponse(success=True)


# ── PATCH /properties/:id/approve ─────────────────────────────────────────────

@router.patch("/{property_id}/approve", response_model=PropertyOut, response_model_by_alias=True)
def approve_property(
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    prop.approval_status = ApprovalStatus.approved
    prop.approved_by = current_user.id
    prop.approved_at = datetime.now(timezone.utc)
    prop.rejection_reason = None
    db.commit()
    db.refresh(prop)
    return _property_to_out(prop, db)


# ── PATCH /properties/:id/reject ──────────────────────────────────────────────

@router.patch("/{property_id}/reject", response_model=PropertyOut, response_model_by_alias=True)
def reject_property(
    property_id: str,
    payload: PropertyRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    prop.approval_status = ApprovalStatus.rejected
    prop.approved_by = current_user.id
    prop.approved_at = datetime.now(timezone.utc)
    prop.rejection_reason = payload.reason
    db.commit()
    db.refresh(prop)
    return _property_to_out(prop, db)
