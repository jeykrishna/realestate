import io
from PIL import Image
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status

from app.schemas.media import MediaUploadResponse
from app.dependencies.auth import require_admin
from app.services.storage_service import upload_file

router = APIRouter(prefix="/media", tags=["Media"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _verify_image_bytes(content: bytes) -> None:
    """Validate that bytes are a real image using Pillow (magic-byte check)."""
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File does not appear to be a valid image.",
        )


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    type: str = Form(..., description="hero | gallery | city"),
    property_id: str = Form(None),
    _: object = Depends(require_admin),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {ALLOWED_TYPES}",
        )

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10 MB",
        )

    _verify_image_bytes(content)

    url, key = await upload_file(
        content=content,
        filename=file.filename,
        content_type=file.content_type,
        folder=f"properties/{property_id}" if property_id else type,
    )

    return MediaUploadResponse(url=url, key=key)
