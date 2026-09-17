from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    url: str
    key: str
