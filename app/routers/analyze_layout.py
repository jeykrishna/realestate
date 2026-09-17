"""
POST /api/v1/analyze-layout
Upload a plot layout image — Claude AI extracts all plot and road data.
Requires: multipart/form-data with field 'image' (PNG/JPG/WEBP, max 10 MB)
Auth: Admin only
"""

import io
import base64
import json
import logging
import anthropic
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from app.dependencies.auth import require_admin
from app.config import get_settings

router = APIRouter(prefix="/analyze-layout", tags=["AI Layout Analysis"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB


class RoadOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    orientation: str
    position: int
    start_cell: int = Field(serialization_alias="startCell")
    end_cell: int = Field(serialization_alias="endCell")


class PlotExtracted(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plot_number: str = Field(serialization_alias="plotNumber")
    block: Optional[str] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    sqft: Optional[int] = None
    facing: Optional[str] = None
    grid_row: int = Field(serialization_alias="gridRow")
    grid_col: int = Field(serialization_alias="gridCol")
    status: str = "available"


class AnalyzeLayoutResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    layout_name: Optional[str] = Field(default=None, serialization_alias="layoutName")
    blocks: list[str] = []
    grid_rows: int = Field(serialization_alias="gridRows")
    grid_cols: int = Field(serialization_alias="gridCols")
    plots: list[PlotExtracted] = []
    roads: list[RoadOut] = []


_SYSTEM_PROMPT = """You are a real-estate layout analyser.
Given an image of a plot layout / site plan, extract the following as JSON:
{
  "layoutName": "<project name if visible>",
  "blocks": ["A-BLOCK", ...],
  "gridRows": <int>,
  "gridCols": <int>,
  "plots": [
    {
      "plotNumber": "<e.g. 1 or A1>",
      "block": "<block name or null>",
      "width": <feet>,
      "depth": <feet>,
      "sqft": <int>,
      "facing": "<north|south|east|west|null>",
      "gridRow": <1-based int>,
      "gridCol": <1-based int>,
      "status": "available"
    }
  ],
  "roads": [
    {
      "label": "<e.g. 33ft Road (Main)>",
      "orientation": "horizontal|vertical",
      "position": <row or col number where road sits>,
      "startCell": <1-based int>,
      "endCell": <1-based int>
    }
  ]
}
Return ONLY the JSON — no markdown fences, no commentary."""


def _verify_image_bytes(content: bytes) -> None:
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File does not appear to be a valid image.",
        )


@router.post("", response_model=AnalyzeLayoutResponse, response_model_by_alias=True)
async def analyze_layout(
    image: UploadFile = File(...),
    _: object = Depends(require_admin),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {image.content_type}. Allowed: PNG, JPG, WEBP.",
        )

    contents = await image.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image exceeds 10 MB limit.",
        )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image provided.",
        )

    _verify_image_bytes(contents)

    b64_image = base64.standard_b64encode(contents).decode("utf-8")
    media_type = image.content_type

    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": _SYSTEM_PROMPT},
                    ],
                }
            ],
        )
    except Exception as exc:
        logger.error("AI layout analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis failed. Please try again.",
        )

    raw_text = msg.content[0].text.strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned invalid JSON. Try a clearer image.",
        )

    plots = [
        PlotExtracted(
            plot_number=str(p.get("plotNumber", p.get("plot_number", ""))),
            block=p.get("block"),
            width=p.get("width"),
            depth=p.get("depth"),
            sqft=p.get("sqft"),
            facing=p.get("facing"),
            grid_row=int(p.get("gridRow", p.get("grid_row", 1))),
            grid_col=int(p.get("gridCol", p.get("grid_col", 1))),
            status=p.get("status", "available"),
        )
        for p in data.get("plots", [])
    ]

    roads = [
        RoadOut(
            label=r.get("label", ""),
            orientation=r.get("orientation", "horizontal"),
            position=int(r.get("position", 1)),
            start_cell=int(r.get("startCell", r.get("start_cell", 1))),
            end_cell=int(r.get("endCell", r.get("end_cell", 1))),
        )
        for r in data.get("roads", [])
    ]

    return AnalyzeLayoutResponse(
        layout_name=data.get("layoutName"),
        blocks=data.get("blocks", []),
        grid_rows=int(data.get("gridRows", 1)),
        grid_cols=int(data.get("gridCols", 1)),
        plots=plots,
        roads=roads,
    )
