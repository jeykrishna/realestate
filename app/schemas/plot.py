from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
from datetime import datetime
from app.models.plot import PlotStatus


# ── Road / Layout ─────────────────────────────────────────────────────────────

class RoadConfig(BaseModel):
    """Road definition used in layoutConfig (grid layouts)."""
    label: str
    orientation: str                    # "horizontal" | "vertical"
    position: int
    start_cell: int = Field(serialization_alias="startCell", validation_alias="startCell", default=1)
    end_cell: int = Field(serialization_alias="endCell", validation_alias="endCell", default=1)

    model_config = ConfigDict(populate_by_name=True)


class ViewpointData(BaseModel):
    """A single 360° walkthrough viewpoint — an uploaded photo with admin-editable
    label/description text (defaults come from the frontend's VIEWPOINT_META)."""
    url: str
    label: str = ""
    desc: str = ""


class LayoutConfig(BaseModel):
    """Plot layout config — either a grid "seat map" or an SVG-polygon "image map"."""
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["grid", "image"] = "grid"

    # Grid layout
    rows: Optional[int] = None
    cols: Optional[int] = None
    roads: list[RoadConfig] = []

    # Image-map layout
    image_url: Optional[str] = Field(default=None, alias="imageUrl")
    img_width: Optional[int] = Field(default=None, alias="imgWidth")
    img_height: Optional[int] = Field(default=None, alias="imgHeight")

    # 360° walkthrough images, keyed by viewpoint id — independent of layout type
    viewpoints: dict[str, ViewpointData] = {}


# ── Plot ──────────────────────────────────────────────────────────────────────

class PlotOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    property_id: str = Field(serialization_alias="propertyId")
    plot_number: str = Field(serialization_alias="plotNumber")
    sqft: int
    length: Optional[float] = None      # from dimensions.width
    breadth: Optional[float] = None     # from dimensions.depth
    facing: Optional[str] = None
    road_width: Optional[int] = Field(default=None, serialization_alias="roadWidth")
    price: Optional[int] = None
    status: str
    notes: Optional[str] = None
    grid_row: int = Field(serialization_alias="gridRow")
    grid_col: int = Field(serialization_alias="gridCol")
    points: Optional[str] = None        # SVG polygon points (image-map plots)
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt")


class PlotListResponse(BaseModel):
    """Combined plots + layoutConfig response."""
    layout_config: Optional[LayoutConfig] = Field(default=None, serialization_alias="layoutConfig")
    plots: list[PlotOut]

    model_config = ConfigDict(populate_by_name=True)


class PlotStatusUpdate(BaseModel):
    status: PlotStatus


class PlotUpdateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    plot: dict   # {id, status}


# ── Plot Config (legacy / admin endpoint) ─────────────────────────────────────

class GridLabels(BaseModel):
    north: Optional[str] = None
    south: Optional[str] = None
    east: Optional[str] = None
    west: Optional[str] = None


class PlotConfigOut(BaseModel):
    property_id: str
    layout_type: str = "grid"
    rows: Optional[int] = None
    cols: Optional[int] = None
    roads: list[dict] = []
    labels: Optional[GridLabels] = None
    image_url: Optional[str] = None
    img_width: Optional[int] = None
    img_height: Optional[int] = None
    viewpoints: dict[str, ViewpointData] = {}

    model_config = ConfigDict(from_attributes=True)


class PlotConfigResponse(BaseModel):
    config: PlotConfigOut


# ── Layout Save ───────────────────────────────────────────────────────────────

class PlotInput(BaseModel):
    """A single plot entry sent by the frontend when saving a layout."""
    model_config = ConfigDict(populate_by_name=True)

    plot_number: str = Field(validation_alias="plotNumber")
    sqft: int
    length: Optional[float] = None      # stored as dimensions.width
    breadth: Optional[float] = None     # stored as dimensions.depth
    facing: Optional[str] = None
    road_width: Optional[int] = Field(default=None, validation_alias="roadWidth")
    price: Optional[int] = None
    status: PlotStatus = PlotStatus.available
    notes: Optional[str] = None
    grid_row: int = Field(default=0, validation_alias="gridRow")
    grid_col: int = Field(default=0, validation_alias="gridCol")
    points: Optional[str] = None        # SVG polygon points (image-map plots)
    block: Optional[str] = None         # from AI analysis


class LayoutSaveRequest(BaseModel):
    layout_config: LayoutConfig = Field(validation_alias="layoutConfig")
    plots: list[PlotInput]

    model_config = ConfigDict(populate_by_name=True)


class LayoutSaveResponse(BaseModel):
    success: bool
    saved_plots: int = Field(serialization_alias="savedPlots")
    message: str

    model_config = ConfigDict(populate_by_name=True)
