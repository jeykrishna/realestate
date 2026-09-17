from fastapi import APIRouter, Depends, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.analytics import AnalyticsEvent, EventType
from app.models.property import Property
from app.models.enquiry import Enquiry
from app.schemas.analytics import (
    TrackEventRequest, TrackEventResponse,
    AnalyticsSummaryResponse, AnalyticsSummary,
    DailyViewEntry, PropertyAnalytics, CategoryEntry,
)
from app.dependencies.auth import require_admin
from app.utils.limiter import limiter

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _log_event(event: TrackEventRequest):
    # Runs as a background task AFTER the request returns, so the request-scoped
    # session is already closed — open and own a fresh one here.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        record = AnalyticsEvent(
            property_id=event.property_id,
            plot_id=event.plot_id,
            event_type=event.event_type,
            session_id=event.session_id,
            timestamp=event.timestamp or datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


def _build_summary(
    db: Session,
    property_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> AnalyticsSummaryResponse:
    q = db.query(AnalyticsEvent)
    if property_id:
        q = q.filter(AnalyticsEvent.property_id == property_id)
    if start_date:
        q = q.filter(AnalyticsEvent.timestamp >= start_date)
    if end_date:
        q = q.filter(AnalyticsEvent.timestamp <= end_date)

    events = q.all()

    total_views = sum(1 for e in events if e.event_type == EventType.view)
    phone_clicks = sum(1 for e in events if e.event_type == EventType.phone_click)
    whatsapp_clicks = sum(1 for e in events if e.event_type == EventType.whatsapp_click)
    enquiry_submits = sum(1 for e in events if e.event_type == EventType.enquiry_submit)

    # views over time
    daily_map: dict[str, int] = {}
    for e in events:
        if e.event_type == EventType.view and e.timestamp:
            day = e.timestamp.strftime("%Y-%m-%d")
            daily_map[day] = daily_map.get(day, 0) + 1
    views_over_time = [DailyViewEntry(date=d, count=c) for d, c in sorted(daily_map.items())]

    # per-property breakdown
    prop_stats: dict[str, dict] = {}
    for e in events:
        pid = e.property_id
        if pid not in prop_stats:
            prop_stats[pid] = {"views": 0, "phone_clicks": 0, "whatsapp_clicks": 0, "enquiries": 0}
        if e.event_type == EventType.view:
            prop_stats[pid]["views"] += 1
        elif e.event_type == EventType.phone_click:
            prop_stats[pid]["phone_clicks"] += 1
        elif e.event_type == EventType.whatsapp_click:
            prop_stats[pid]["whatsapp_clicks"] += 1
        elif e.event_type == EventType.enquiry_submit:
            prop_stats[pid]["enquiries"] += 1

    by_property = []
    for pid, stats in sorted(prop_stats.items(), key=lambda x: x[1]["views"], reverse=True)[:10]:
        prop = db.query(Property).filter(Property.id == pid).first()
        by_property.append(PropertyAnalytics(
            property_id=pid,
            property_name=prop.name if prop else pid,
            views=stats["views"],
            phone_clicks=stats["phone_clicks"],
            whatsapp_clicks=stats["whatsapp_clicks"],
            enquiries=stats["enquiries"],
        ))

    # category breakdown
    cat_map: dict[str, int] = {}
    for e in events:
        if e.event_type == EventType.view:
            prop = db.query(Property).filter(Property.id == e.property_id).first()
            if prop:
                cat = prop.category.value
                cat_map[cat] = cat_map.get(cat, 0) + 1
    category_breakdown = [CategoryEntry(category=c, count=n) for c, n in cat_map.items()]

    return AnalyticsSummaryResponse(
        summary=AnalyticsSummary(
            total_views=total_views,
            phone_clicks=phone_clicks,
            whatsapp_clicks=whatsapp_clicks,
            enquiries=enquiry_submits,
        ),
        by_property=by_property,
        views_over_time=views_over_time,
        category_breakdown=category_breakdown,
    )


# ── POST /analytics/event  (doc path) ────────────────────────────────────────

@router.post("/event", response_model=TrackEventResponse, status_code=202)
@limiter.limit("30/minute")
async def track_event(
    request: Request,
    payload: TrackEventRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background.add_task(_log_event, payload)
    return TrackEventResponse(success=True)


# ── POST /analytics/track  (legacy path) ─────────────────────────────────────

@router.post("/track", response_model=TrackEventResponse, status_code=202, include_in_schema=False)
@limiter.limit("30/minute")
async def track_event_legacy(
    request: Request,
    payload: TrackEventRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background.add_task(_log_event, payload)
    return TrackEventResponse(success=True)


# ── GET /analytics  (doc path) ────────────────────────────────────────────────

@router.get("", response_model=AnalyticsSummaryResponse, response_model_by_alias=True)
def analytics_summary(
    start_date: Optional[str] = Query(None, alias="from"),
    end_date: Optional[str] = Query(None, alias="to"),
    property_id: Optional[str] = Query(None, alias="propertyId"),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    return _build_summary(db, property_id, start_date, end_date)


# ── GET /analytics/summary  (legacy path) ────────────────────────────────────

@router.get("/summary", response_model=AnalyticsSummaryResponse, response_model_by_alias=True, include_in_schema=False)
def analytics_summary_legacy(
    start_date: Optional[str] = Query(None, alias="startDate"),
    end_date: Optional[str] = Query(None, alias="endDate"),
    property_id: Optional[str] = Query(None, alias="propertyId"),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    return _build_summary(db, property_id, start_date, end_date)
