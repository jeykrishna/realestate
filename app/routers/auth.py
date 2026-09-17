import re
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse, LogoutResponse,
    UserOut,
)
from app.utils.jwt import create_access_token, decode_access_token, add_to_blocklist
from app.utils.id_gen import make_id
from app.utils.limiter import limiter
from app.dependencies.auth import get_current_user, require_admin
from app.services.otp_service import store_otp, verify_otp_code
from app.services.email_service import send_otp_email
from app.services.sms_service import send_otp_sms
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False)
_settings = get_settings()


def _normalize_phone(raw: str) -> str:
    """Reduce any phone input to its bare 10-digit national form.

    Strips all non-digits and a leading 91 country code. (Replaces the old
    `phone.lstrip("+91")`, which removed *characters* + / 9 / 1 anywhere at the
    start and mangled numbers like 919XXXXXXXXX.)
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    access_token: Optional[str] = Cookie(default=None),
    setup_token: Optional[str] = Header(default=None, alias="X-Setup-Token"),
):
    """
    Create a new admin or owner user.

    - If admins already exist → requires a valid admin JWT token.
    - If NO admin exists yet (first-time setup) → permitted ONLY when SETUP_TOKEN
      is configured and the caller supplies a matching X-Setup-Token header.
      With SETUP_TOKEN unset (the default) the first admin must be created via
      seed.py — anonymous admin self-registration is not possible.
    """
    admin_exists = db.query(User).filter(User.role == UserRole.admin).first() is not None

    if admin_exists:
        # Require admin auth for all subsequent registrations
        token = credentials.credentials if credentials else access_token
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")
        from app.utils.jwt import decode_access_token, is_blocklisted
        token_payload = decode_access_token(token)
        if not token_payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        jti = token_payload.get("jti")
        if jti and await is_blocklisted(jti):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
        caller_role = token_payload.get("role")
        if caller_role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can register new users")
    else:
        # Bootstrap path — locked behind an out-of-band setup token.
        if not _settings.SETUP_TOKEN or not setup_token or not secrets.compare_digest(
            setup_token, _settings.SETUP_TOKEN
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is closed.",
            )

    # Check duplicates
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")

    user = User(
        id=make_id("usr"),
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        role=UserRole(payload.role),
        property_ids=payload.property_ids,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_out = UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        property_ids=user.property_ids or [],
    )
    return RegisterResponse(
        success=True,
        message=f"{'Admin' if user.role == UserRole.admin else 'Owner'} account created successfully",
        user=user_out,
    )


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut, response_model_by_alias=True)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        property_ids=current_user.property_ids or [],
    )


# ── Send OTP ──────────────────────────────────────────────────────────────────

@router.post("/send-otp", response_model=SendOTPResponse)
@limiter.limit("3/15minutes")
async def send_otp(request: Request, payload: SendOTPRequest, db: Session = Depends(get_db)):
    otp = f"{secrets.randbelow(900000) + 100000}"

    # Always return the same response whether or not the account exists, so the
    # endpoint can't be used to enumerate registered emails / phone numbers.
    if payload.email:
        user = db.query(User).filter(User.email == payload.email).first()
        if user:
            await store_otp(payload.email, otp)
            await send_otp_email(email=payload.email, otp=otp, name=user.name)
        return SendOTPResponse(success=True, message="If an account exists, an OTP has been sent.")
    else:
        digits = _normalize_phone(payload.phone)
        user = db.query(User).filter(User.phone == digits).first()
        if user:
            await store_otp(digits, otp)
            await send_otp_sms(phone="+91" + digits, otp=otp)
        return SendOTPResponse(success=True, message="If an account exists, an OTP has been sent.")


# ── Verify OTP ────────────────────────────────────────────────────────────────

@router.post("/verify-otp", response_model=VerifyOTPResponse, response_model_by_alias=True)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request,
    payload: VerifyOTPRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    if payload.email:
        identifier = payload.email
        user = db.query(User).filter(User.email == identifier).first()
    else:
        identifier = _normalize_phone(payload.phone)
        user = db.query(User).filter(User.phone == identifier).first()

    valid = await verify_otp_code(identifier, payload.otp)
    # No OTP is ever stored for a non-existent account, so an invalid result
    # here also covers the "no such user" case — return one generic error
    # either way to avoid leaking which accounts exist.
    if not valid or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP")

    token = create_access_token({"sub": user.id, "role": user.role})
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, secure=True, samesite="strict", max_age=86400,
    )

    user_out = UserOut(
        id=user.id, name=user.name, email=user.email,
        phone=user.phone, role=user.role,
        property_ids=user.property_ids or [],
    )
    return VerifyOTPResponse(success=True, user=user_out, token=token)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    access_token: Optional[str] = Cookie(default=None),
    _: User = Depends(get_current_user),
):
    token = credentials.credentials if credentials else access_token
    if token:
        payload = decode_access_token(token)
        if payload and "jti" in payload and "exp" in payload:
            await add_to_blocklist(payload["jti"], payload["exp"])
    response.delete_cookie("access_token")
    return LogoutResponse(success=True)
