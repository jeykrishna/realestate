"""SMS delivery via AWS SNS (boto3).

Falls back to console logging in development mode when no credentials are set.
"""
from __future__ import annotations
import logging
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sns_client():
    return boto3.client(
        "sns",
        region_name=settings.AWS_SNS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def send_otp_sms(phone: str, otp: str) -> None:
    """Send OTP via SMS to the given phone number (E.164 format, e.g. +919876543210)."""

    if settings.APP_ENV == "development" and not settings.AWS_ACCESS_KEY_ID:
        logger.info("=== DEV SMS (AWS SNS not configured) ===")
        logger.info(f"To: {phone} | OTP: {otp}")
        return

    message = f"Your PlotBook login code is: {otp}\nValid for 10 minutes. Do not share this code."

    try:
        client = _get_sns_client()
        client.publish(
            PhoneNumber=phone,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",
                },
                "AWS.SNS.SMS.SenderID": {
                    "DataType": "String",
                    "StringValue": "PlotBook",
                },
            },
        )
        logger.info(f"SNS SMS sent to {phone}")
    except ClientError as exc:
        logger.error(f"SNS SMS failed to {phone}: {exc}")
        raise
