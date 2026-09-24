import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.enquiry import Enquiry, EnquiryStatus
from app.models.property import Property
from app.models.plot import Plot
from app.models.user import User, UserRole
from app.schemas.enquiry import (
    EnquiryCreate, EnquiryCreateResponse, EnquiryListResponse,
    EnquiryOut, EnquiryStatusUpdate, EnquiryUpdateResponse, Pagination,
)
from app.dependencies.auth import require_owner_or_admin
from app.utils.id_gen import make_id
from app.utils.limiter import limiter
from app.services.email_service import send_enquiry_notification

router = APIRouter(prefix="/enquiries", tags=["Enquiries"])


def _owned_property_ids(db: Session, admin_id: str) -> list[str]:
    """Property IDs created by a given admin, for scoping their enquiry view."""
    return [pid for (pid,) in db.query(Property.id).filter(Property.owner_id == admin_id).all()]


def _enquiry_to_out(e: Enquiry, db: Session) -> EnquiryOut:
    prop = db.query(Property).filter(Property.id == e.property_id).first()
    plot = db.query(Plot).filter(Plot.id == e.plot_id).first() if e.plot_id else None
    return EnquiryOut(
        id=e.id,
        name=e.name,
        email=e.email,
        phone=e.phone,
        city=e.city,
        message=e.message,
        property_id=e.property_id,
        property_name=prop.name if prop else None,
        plot_id=e.plot_id,
        plot_number=plot.plot_number if plot else None,
        status=e.status.value,
        created_at=e.created_at,
    )


# ── POST /enquiries ───────────────────────────────────────────────────────────

@router.post("", response_model=EnquiryCreateResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_enquiry(request: Request, payload: EnquiryCreate, db: Session = Depends(get_db)):
    enquiry = Enquiry(
        id=make_id("enq"),
        property_id=payload.property_id,
        plot_id=payload.plot_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        city=payload.city,
        message=payload.message,
        status=EnquiryStatus.new,
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    try:
        await send_enquiry_notification(enquiry=enquiry, db=db)
    except Exception:
        pass

    return EnquiryCreateResponse(success=True, enquiry_id=enquiry.id)


# ── GET /enquiries/export ─────────────────────────────────────────────────────

@router.get("/export")
def export_enquiries(
    propertyId: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    if current_user.role == UserRole.owner:
        if propertyId not in (current_user.property_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    elif current_user.role == UserRole.admin:
        prop = db.query(Property).filter(Property.id == propertyId).first()
        if not prop or prop.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")

    enquiries = db.query(Enquiry).filter(Enquiry.property_id == propertyId).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Phone", "City", "Message", "Plot", "Status", "Date"])
    for e in enquiries:
        writer.writerow([
            e.name, e.email, e.phone, e.city or "",
            e.message or "", e.plot_id or "", e.status,
            e.created_at.strftime("%Y-%m-%d") if e.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.read().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=enquiries-{propertyId}.csv"},
    )


# ── GET /enquiries ────────────────────────────────────────────────────────────

@router.get("", response_model=EnquiryListResponse, response_model_by_alias=True)
def list_enquiries(
    propertyId: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    q = db.query(Enquiry)

    if current_user.role == UserRole.owner:
        owner_property_ids = current_user.property_ids or []
        q = q.filter(Enquiry.property_id.in_(owner_property_ids))
    elif current_user.role == UserRole.admin:
        # Regular admins only see enquiries for properties they created.
        # Super admins keep the full, unfiltered view.
        q = q.filter(Enquiry.property_id.in_(_owned_property_ids(db, current_user.id)))

    if propertyId:
        q = q.filter(Enquiry.property_id == propertyId)
    if status:
        q = q.filter(Enquiry.status == status)

    total = q.count()
    enquiries = q.order_by(Enquiry.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return EnquiryListResponse(
        data=[_enquiry_to_out(e, db) for e in enquiries],
        pagination=Pagination(page=page, limit=limit, total=total),
    )


# ── PATCH /enquiries/:id/status ───────────────────────────────────────────────

@router.patch("/{enquiry_id}/status", response_model=EnquiryUpdateResponse)
def update_enquiry_status(
    enquiry_id: str,
    payload: EnquiryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    enquiry = db.query(Enquiry).filter(Enquiry.id == enquiry_id).first()
    if not enquiry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enquiry not found")

    if current_user.role == UserRole.owner:
        if enquiry.property_id not in (current_user.property_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your enquiry")
    elif current_user.role == UserRole.admin:
        prop = db.query(Property).filter(Property.id == enquiry.property_id).first()
        if not prop or prop.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your enquiry")

    enquiry.status = payload.status
    db.commit()
    db.refresh(enquiry)
    return EnquiryUpdateResponse(success=True, id=enquiry.id, status=enquiry.status.value)


# ── PUT /enquiries/:id (legacy — kept for backwards compat) ───────────────────

@router.put("/{enquiry_id}", response_model=EnquiryUpdateResponse)
def update_enquiry_status_put(
    enquiry_id: str,
    payload: EnquiryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    return update_enquiry_status(enquiry_id, payload, db, current_user)
