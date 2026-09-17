from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.plot import Plot, PlotStatus
from app.models.property import Property, PropertyStatus
from app.models.plot_config import PlotConfig
from app.schemas.plot import (
    PlotListResponse, PlotOut, PlotStatusUpdate, PlotUpdateResponse,
    PlotConfigResponse, PlotConfigOut, GridLabels,
    LayoutSaveRequest, LayoutSaveResponse, LayoutConfig, RoadConfig,
)
from app.dependencies.auth import require_owner_or_admin
from app.models.user import User, UserRole
from app.utils.id_gen import make_id
from app.utils.limiter import limiter


router = APIRouter(prefix="/plots", tags=["Plots"])


def _plot_to_out(p: Plot) -> PlotOut:
    dims = p.dimensions or {}
    length = dims.get("width") if isinstance(dims, dict) else None
    breadth = dims.get("depth") if isinstance(dims, dict) else None
    return PlotOut(
        id=p.id,
        property_id=p.property_id,
        plot_number=p.plot_number,
        sqft=p.sqft,
        length=length,
        breadth=breadth,
        facing=p.facing,
        road_width=p.road_width,
        price=p.price,
        status=p.status.value,
        notes=p.notes,
        grid_row=p.grid_row,
        grid_col=p.grid_col,
        points=p.polygon,
        updated_at=p.updated_at,
    )


def _config_to_layout(config: PlotConfig) -> LayoutConfig:
    if config.layout_type == "image":
        return LayoutConfig(
            type="image",
            image_url=config.image_url,
            img_width=config.img_width,
            img_height=config.img_height,
        )

    roads = []
    for r in (config.roads or []):
        if isinstance(r, dict):
            roads.append(RoadConfig(
                label=r.get("label", ""),
                orientation=r.get("orientation", "horizontal"),
                position=r.get("position", 1),
                start_cell=r.get("startCell", r.get("start_cell", 1)),
                end_cell=r.get("endCell", r.get("end_cell", 1)),
            ))
    return LayoutConfig(type="grid", rows=config.rows, cols=config.cols, roads=roads)


def _auto_hide_property(db: Session, property_id: str):
    plots = db.query(Plot).filter(Plot.property_id == property_id).all()
    if plots and all(p.status != PlotStatus.available for p in plots):
        prop = db.query(Property).filter(Property.id == property_id).first()
        if prop:
            prop.status = PropertyStatus.archived
            db.commit()


# ── GET /plots?propertyId=xxx ─────────────────────────────────────────────────

@router.get("", response_model=PlotListResponse, response_model_by_alias=True)
@limiter.limit("60/minute")
def list_plots(
    request: Request,
    propertyId: str = Query(..., description="Property ID to fetch plots for"),
    db: Session = Depends(get_db),
):
    plots = (
        db.query(Plot)
        .filter(Plot.property_id == propertyId)
        .order_by(Plot.grid_row, Plot.grid_col)
        .all()
    )

    config = db.query(PlotConfig).filter(PlotConfig.property_id == propertyId).first()
    layout_config = _config_to_layout(config) if config else None

    return PlotListResponse(
        layout_config=layout_config,
        plots=[_plot_to_out(p) for p in plots],
    )


# ── PATCH /plots/:plotId/status ───────────────────────────────────────────────

@router.patch("/{plot_id}/status", response_model=PlotUpdateResponse, response_model_by_alias=True)
def update_plot_status(
    plot_id: str,
    payload: PlotStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    plot = db.query(Plot).filter(Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot not found")

    if current_user.role == UserRole.owner:
        if plot.property_id not in (current_user.property_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")

    plot.status = payload.status
    db.commit()

    # Update property available_plots count
    prop = db.query(Property).filter(Property.id == plot.property_id).first()
    if prop:
        prop.available_plots = (
            db.query(Plot)
            .filter(Plot.property_id == plot.property_id, Plot.status == PlotStatus.available)
            .count()
        )
        db.commit()

    _auto_hide_property(db, plot.property_id)
    db.refresh(plot)
    return PlotUpdateResponse(success=True, plot={"id": plot.id, "status": plot.status.value})


# ── PUT /plots/:plotId  (legacy — kept for backwards compat) ──────────────────

@router.put("/{plot_id}", response_model=PlotUpdateResponse, response_model_by_alias=True)
def update_plot_status_put(
    plot_id: str,
    payload: PlotStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    """Legacy PUT endpoint — delegates to PATCH handler logic."""
    return update_plot_status(plot_id, payload, db, current_user)


# ── POST /properties/:propertyId/plots/layout ─────────────────────────────────
# Mounted on properties router — registered here as a separate sub-router

layout_router = APIRouter(prefix="/properties", tags=["Plots"])


@layout_router.post(
    "/{property_id}/plots/layout",
    response_model=LayoutSaveResponse,
    response_model_by_alias=True,
)
def save_layout(
    property_id: str,
    payload: LayoutSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Owners may only publish layouts for properties assigned to them.
    if current_user.role == UserRole.owner:
        if property_id not in (current_user.property_ids or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")

    # Delete existing plots and config for this property
    db.query(Plot).filter(Plot.property_id == property_id).delete()
    db.query(PlotConfig).filter(PlotConfig.property_id == property_id).delete()
    db.commit()

    layout = payload.layout_config

    if layout.type == "image":
        config = PlotConfig(
            id=make_id("cfg"),
            property_id=property_id,
            layout_type="image",
            rows=None,
            cols=None,
            roads=[],
            image_url=layout.image_url,
            img_width=layout.img_width,
            img_height=layout.img_height,
        )
    else:
        roads_data = [
            {
                "label": r.label,
                "orientation": r.orientation,
                "position": r.position,
                "startCell": r.start_cell,
                "endCell": r.end_cell,
            }
            for r in layout.roads
        ]
        config = PlotConfig(
            id=make_id("cfg"),
            property_id=property_id,
            layout_type="grid",
            rows=layout.rows,
            cols=layout.cols,
            roads=roads_data,
        )
    db.add(config)

    # Save plots
    saved = 0
    for plot_in in payload.plots:
        dimensions = None
        if plot_in.length is not None or plot_in.breadth is not None:
            dimensions = {"width": plot_in.length, "depth": plot_in.breadth}

        plot = Plot(
            id=make_id("plt"),
            property_id=property_id,
            plot_number=plot_in.plot_number,
            sqft=plot_in.sqft,
            dimensions=dimensions,
            facing=plot_in.facing,
            road_width=plot_in.road_width,
            price=plot_in.price,
            status=plot_in.status,
            notes=plot_in.notes,
            grid_row=plot_in.grid_row,
            grid_col=plot_in.grid_col,
            polygon=plot_in.points,
        )
        db.add(plot)
        saved += 1

    db.commit()

    # Update property plot counts
    available = sum(1 for p in payload.plots if p.status == PlotStatus.available)
    prop.total_plots = saved
    prop.available_plots = available
    db.commit()

    return LayoutSaveResponse(
        success=True,
        saved_plots=saved,
        message=f"Layout published with {saved} plots.",
    )


# ── GET /plot-configs/:propertyId (legacy endpoint) ───────────────────────────

plot_config_router = APIRouter(prefix="/plot-configs", tags=["Plot Config"])


@plot_config_router.get("/{property_id}", response_model=PlotConfigResponse)
def get_plot_config(property_id: str, db: Session = Depends(get_db)):
    config = db.query(PlotConfig).filter(PlotConfig.property_id == property_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plot config not found")
    return PlotConfigResponse(
        config=PlotConfigOut(
            property_id=config.property_id,
            layout_type=config.layout_type or "grid",
            rows=config.rows,
            cols=config.cols,
            roads=config.roads or [],
            labels=config.labels,
            image_url=config.image_url,
            img_width=config.img_width,
            img_height=config.img_height,
        )
    )
