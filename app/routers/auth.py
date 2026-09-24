import logging
import re
import secrets
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    RegisterRequest, RegisterResponse, RegisterSendOtpRequest,
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse, LogoutResponse,
    LoginRequest, LoginResponse,
    UserOut,
)
from app.utils.jwt import create_access_token, decode_access_token, add_to_blocklist
from app.utils.id_gen import make_id
from app.utils.limiter import limiter
from app.utils.security import hash_password, verify_password
from app.dependencies.auth import get_current_user, require_admin
from app.services.otp_service import store_otp, verify_otp_code
from app.services.email_service import send_otp_email, send_registration_otp_email
from app.services.sms_service import send_otp_sms
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False)
_settings = get_settings()
_logger = logging.getLogger(__name__)


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


def _registration_otp_key(email: str) -> str:
    # Namespaced separately from the login-OTP key so a registration code and
    # a login code for the same email can never collide.
    return f"register:{email}"


# ── Register: send email verification OTP ────────────────────────────────────

@router.post("/register/send-otp", response_model=SendOTPResponse)
@limiter.limit(_settings.RATE_LIMIT_OTP)
async def register_send_otp(
    request: Request,
    payload: RegisterSendOtpRequest,
    db: Session = Depends(get_db),
):
    """Send a verification code to the email an admin/super_admin is
    registering with. Unlike login OTP, this can tell the caller the email is
    already active — that's expected feedback during signup, not an
    enumeration risk."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing and existing.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email already has an account. Please log in instead.",
        )

    otp = f"{secrets.randbelow(900000) + 100000}"
    await store_otp(_registration_otp_key(payload.email), otp)
    try:
        await send_registration_otp_email(
            email=payload.email, otp=otp, name=existing.name if existing else "there"
        )
    except ClientError as exc:
        _logger.error("Failed to send registration OTP to %s: %s", payload.email, exc)
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "MessageRejected":
            detail = (
                "We couldn't send a code to this email address. It hasn't been "
                "verified with our email provider yet — contact your system "
                "administrator to have it verified, then try again."
            )
        else:
            detail = "Could not send the verification email right now. Please try again shortly."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    return SendOTPResponse(success=True, message="Verification code sent to your email.")


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Create a new user of any role. Open registration — no auth required.

    Privileged roles (admin, super_admin) require a matching secret key so
    anyone hitting this endpoint directly can't self-elevate, a verified email
    (via POST /auth/register/send-otp) so no one can register with an email
    they don't control, and a password since they log in with one instead of OTP.

    If the email already belongs to a passwordless admin/super_admin of the
    same role (a legacy account from before password login existed), this
    "claims" it — sets its password — instead of rejecting it as a duplicate.
    """
    is_privileged = payload.role in ("admin", "super_admin")

    if payload.role == "admin" and payload.secret_key != _settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin secret key")
    if payload.role == "super_admin" and payload.secret_key != _settings.SUPER_ADMIN_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid super admin secret key")
    if is_privileged and not payload.password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password is required")
    if is_privileged and not payload.otp:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email verification code is required")
    if is_privileged and not await verify_otp_code(_registration_otp_key(payload.email), payload.otp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired verification code")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        if is_privileged and existing.role == UserRole(payload.role) and not existing.password_hash:
            existing.password_hash = hash_password(payload.password)
            db.commit()
            db.refresh(existing)
            return RegisterResponse(
                success=True,
                message="Password set — you can now log in.",
                user=UserOut(
                    id=existing.id,
                    name=existing.name,
                    email=existing.email,
                    phone=existing.phone,
                    role=existing.role,
                    property_ids=existing.property_ids or [],
                ),
            )
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
        password_hash=hash_password(payload.password) if is_privileged else None,
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
    role_label = {
        UserRole.admin: "Admin",
        UserRole.super_admin: "Super Admin",
        UserRole.owner: "Owner",
    }[user.role]
    return RegisterResponse(
        success=True,
        message=f"{role_label} account created successfully",
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
@limiter.limit(_settings.RATE_LIMIT_OTP)
async def send_otp(request: Request, payload: SendOTPRequest, db: Session = Depends(get_db)):
    otp = f"{secrets.randbelow(900000) + 100000}"

    # Always return the same response whether or not the account exists (or the
    # email/SMS send actually succeeded), so the endpoint can't be used to
    # enumerate registered emails / phone numbers.
    if payload.email:
        user = db.query(User).filter(User.email == payload.email).first()
        if user:
            await store_otp(payload.email, otp)
            try:
                await send_otp_email(email=payload.email, otp=otp, name=user.name)
            except ClientError as exc:
                _logger.error("Failed to send login OTP to %s: %s", payload.email, exc)
        return SendOTPResponse(success=True, message="If an account exists, an OTP has been sent.")
    else:
        digits = _normalize_phone(payload.phone)
        user = db.query(User).filter(User.phone == digits).first()
        if user:
            await store_otp(digits, otp)
            try:
                await send_otp_sms(phone="+91" + digits, otp=otp)
            except Exception as exc:
                _logger.error("Failed to send login OTP SMS to %s: %s", digits, exc)
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


# ── Password login (admin / super admin) ─────────────────────────────────────

@router.post("/login", response_model=LoginResponse, response_model_by_alias=True)
@limiter.limit(_settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()

    # One generic error for "no such user", "no password set" and "wrong
    # password" alike, so this endpoint can't be used to enumerate accounts.
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role not in (UserRole.admin, UserRole.super_admin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

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
    return LoginResponse(success=True, user=user_out, token=token)


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
