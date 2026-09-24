"""Email delivery via AWS SES (boto3).

Falls back to console logging in development mode when no credentials are set.
"""
from __future__ import annotations
import logging
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_ses_client():
    return boto3.client(
        "ses",
        region_name=settings.AWS_SES_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def _send(to: str, subject: str, html: str) -> None:
    if settings.APP_ENV == "development" and not settings.AWS_ACCESS_KEY_ID:
        logger.info("=== DEV EMAIL (AWS SES not configured) ===")
        logger.info(f"To: {to}\nSubject: {subject}\n{html}")
        return

    try:
        client = _get_ses_client()
        client.send_email(
            Source=f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html, "Charset": "UTF-8"}},
            },
        )
        logger.info(f"SES email sent to {to}")
    except ClientError as exc:
        logger.error(f"SES email failed to {to}: {exc}")
        raise


async def send_otp_email(email: str, otp: str, name: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                border:1px solid #e5e7eb;border-radius:8px">
      <h2 style="color:#1d4ed8;margin-bottom:8px">PlotBook Login</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>Your one-time login code is:</p>
      <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#111827;
                  background:#f3f4f6;padding:16px 24px;border-radius:6px;
                  text-align:center;margin:16px 0">{otp}</div>
      <p style="color:#6b7280;font-size:14px">
        This code expires in <strong>10 minutes</strong> and can only be used once.<br>
        If you did not request this, please ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="color:#9ca3af;font-size:12px">PlotBook — Real Estate Plot Management Platform</p>
    </div>
    """
    await _send(to=email, subject="Your PlotBook Login Code", html=html)


async def send_registration_otp_email(email: str, otp: str, name: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                border:1px solid #e5e7eb;border-radius:8px">
      <h2 style="color:#7c3aed;margin-bottom:8px">Verify your PlotBook account</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <p>Use this code to verify your email and finish creating your admin account:</p>
      <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#111827;
                  background:#f3f4f6;padding:16px 24px;border-radius:6px;
                  text-align:center;margin:16px 0">{otp}</div>
      <p style="color:#6b7280;font-size:14px">
        This code expires in <strong>10 minutes</strong> and can only be used once.<br>
        If you did not request this, please ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
      <p style="color:#9ca3af;font-size:12px">PlotBook — Real Estate Plot Management Platform</p>
    </div>
    """
    await _send(to=email, subject="Verify your email — PlotBook", html=html)


async def send_enquiry_notification(enquiry, db) -> None:
    from app.models.property import Property
    from app.models.user import User

    prop = db.query(Property).filter(Property.id == enquiry.property_id).first()
    if not prop:
        return
    owner = db.query(User).filter(User.id == prop.owner_id).first()
    if not owner:
        return

    plot_info = f"Plot #{enquiry.plot_id}" if enquiry.plot_id else "General enquiry"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:32px;
                border:1px solid #e5e7eb;border-radius:8px">
      <h2 style="color:#16a34a">New Enquiry — {prop.name}</h2>
      <p>You have received a new enquiry on <strong>{prop.name}</strong>.</p>
      <table style="width:100%;border-collapse:collapse;margin-top:16px">
        <tr><td style="padding:8px;color:#6b7280;width:120px">Name</td>
            <td style="padding:8px;font-weight:600">{enquiry.name}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Phone</td>
            <td style="padding:8px;font-weight:600">{enquiry.phone}</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Email</td>
            <td style="padding:8px">{enquiry.email}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">City</td>
            <td style="padding:8px">{enquiry.city or "—"}</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Interest</td>
            <td style="padding:8px">{plot_info}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Message</td>
            <td style="padding:8px">{enquiry.message or "—"}</td></tr>
      </table>
      <p style="margin-top:24px;color:#6b7280;font-size:14px">
        Log in to your PlotBook dashboard to manage this enquiry.
      </p>
    </div>
    """
    await _send(to=owner.email, subject=f"New Enquiry — {prop.name}", html=html)
