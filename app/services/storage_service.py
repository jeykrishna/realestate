"""File storage service.

In production, uploads to AWS S3 (or Cloudflare R2 with S3-compatible API).
In development (no AWS credentials), saves to local /tmp/plotbook-uploads/.
"""
from __future__ import annotations
import os
import uuid
import logging
from pathlib import Path
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def upload_file(
    content: bytes,
    filename: str,
    content_type: str,
    folder: str = "uploads",
) -> tuple[str, str]:
    """Upload file and return (public_url, s3_key)."""
    ext = Path(filename).suffix.lower() or ".jpg"
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    if settings.MEDIA_STORAGE.lower() == "s3":
        if not (
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.S3_BUCKET_NAME
        ):
            raise RuntimeError(
                "MEDIA_STORAGE=s3 but AWS credentials or S3_BUCKET_NAME are not configured"
            )
        return await _upload_s3(content, key, content_type)
    return _upload_local(content, key)


async def _upload_s3(content: bytes, key: str, content_type: str) -> tuple[str, str]:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        s3 = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        # Prefer the CDN origin; fall back to the S3 virtual-hosted URL
        # so media is reachable even before a CDN is configured.
        base = settings.CDN_BASE_URL.rstrip("/") or (
            f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com"
        )
        url = f"{base}/{key}"
        return url, key
    except (BotoCoreError, ClientError) as exc:
        logger.error(f"S3 upload failed: {exc}")
        raise


def _upload_local(content: bytes, key: str) -> tuple[str, str]:
    upload_dir = Path("/tmp/plotbook-uploads") / Path(key).parent
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = Path("/tmp/plotbook-uploads") / key
    dest.write_bytes(content)
    url = f"/static/uploads/{key}"
    logger.info(f"[DEV] File saved locally: {dest}")
    return url, key
