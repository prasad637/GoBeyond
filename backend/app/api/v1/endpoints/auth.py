import uuid
import secrets
import hashlib
import datetime
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User, UserProfile, Role, RefreshToken
from app.models.partner import Partner
from app.models.location import Location
from app.models.audit import AuditLog
from app.services.otp import otp_service
from app.schemas.auth import (
    Token,
    UserRegisterRequest,
    UserLoginRequest,
    OTPRequest,
    OTPVerifyRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserProfileResponse,
    UserUpdateRequest
)
from app.api.deps import get_current_user
from app.core.rate_limit import auth_rate_limiter, otp_rate_limiter, password_reset_rate_limiter

router = APIRouter()


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token_record(db: Session, user_id: int, family_id: Optional[str] = None) -> Tuple[str, RefreshToken]:
    """Creates a new single-use refresh token record."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    fam_id = family_id or str(uuid.uuid4())
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=token_hash,
        family_id=fam_id,
        is_revoked=False,
        expires_at=expires_at,
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(record)
    return raw_token, record


def set_auth_cookies(response: Response, raw_refresh_token: str):
    """Sets secure HttpOnly refresh token cookie and CSRF token cookie."""
    cookie_secure = (
        settings.COOKIE_SECURE
        if settings.COOKIE_SECURE is not None
        else (settings.ENVIRONMENT == "production")
    )
    # HttpOnly refresh cookie (Restricted to /api/v1/auth)
    response.set_cookie(
        key="gobeyond_refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    # Non-HttpOnly CSRF cookie for client-side extraction in double-submit pattern
    # Path="/" ensures document.cookie can read the token across all frontend SPA routes.
    csrf_token = secrets.token_hex(16)
    response.set_cookie(
        key="gobeyond_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )


def clear_auth_cookies(response: Response):
    """Clears all session authentication cookies."""
    response.delete_cookie(key="gobeyond_refresh_token", path="/api/v1/auth")
    response.delete_cookie(key="gobeyond_csrf_token", path="/")


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_rate_limiter)])
def register(req: UserRegisterRequest, response: Response, db: Session = Depends(get_db)):
    # Check duplicate email
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )
    # Check duplicate phone
    if db.query(User).filter(User.phone == req.phone).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this mobile number already exists."
        )

    # Determine role (administrative roles forbidden for public registration)
    raw_role = (req.role or "customer").strip().lower()
    if raw_role in ["super_admin", "admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration cannot assign administrative roles."
        )

    requested_role = raw_role if raw_role in [
        "customer", "partner_restaurant", "partner_cinema", "partner_event", "partner_sports"
    ] else "customer"

    is_partner = requested_role.startswith("partner_")
    initial_account_status = "PENDING_APPROVAL" if is_partner else "ACTIVE"

    role_record = db.query(Role).filter(Role.name == requested_role).first()
    if not role_record:
        role_record = Role(name=requested_role)
        db.add(role_record)
        db.flush()

    user = User(
        email=req.email.lower(),
        phone=req.phone,
        full_name=req.full_name,
        hashed_password=get_password_hash(req.password),
        is_active=True,
        is_verified=False,
        account_status=initial_account_status
    )
    user.roles.append(role_record)
    db.add(user)
    db.flush()

    if is_partner:
        p_type_map = {
            "partner_restaurant": "RESTAURANT",
            "partner_cinema": "CINEMA",
            "partner_event": "EVENT",
            "partner_sports": "SPORTS"
        }
        partner = Partner(
            user_id=user.id,
            business_name=f"{req.full_name}'s Business",
            partner_type=p_type_map.get(requested_role, "RESTAURANT"),
            contact_email=req.email.lower(),
            contact_phone=req.phone,
            status="PENDING_APPROVAL"
        )
        db.add(partner)
        db.flush()

    # Create associated profile
    profile = UserProfile(
        user_id=user.id,
        city_id=req.city_id,
        locality_id=req.locality_id,
        preferred_language="English"
    )
    db.add(profile)

    # Issue refresh token record
    raw_refresh_token, _ = create_refresh_token_record(db, user.id)

    # Log audit
    audit = AuditLog(
        user_id=user.id,
        action="USER_REGISTRATION",
        resource_type="USER",
        resource_id=str(user.id),
        details={"role": requested_role, "email": req.email}
    )
    db.add(audit)
    db.commit()

    token = create_access_token(subject=user.id, role=requested_role)
    set_auth_cookies(response, raw_refresh_token)

    return Token(
        access_token=token,
        token_type="bearer",
        role=requested_role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        refresh_token=raw_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
def login(req: UserLoginRequest, response: Response, db: Session = Depends(get_db)):
    login_str = req.login.strip().lower()
    user = db.query(User).filter(
        (User.email == login_str) | (User.phone == req.login.strip())
    ).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your email/mobile and password."
        )

    if not user.is_active or getattr(user, "account_status", "ACTIVE") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is deactivated or suspended. Contact support."
        )

    # Determine primary role
    roles = [r.name for r in user.roles]
    primary_role = "customer"
    for priority_role in ["super_admin", "partner_cinema", "partner_restaurant", "partner_event", "partner_sports", "customer"]:
        if priority_role in roles:
            primary_role = priority_role
            break

    # Issue refresh token record
    raw_refresh_token, _ = create_refresh_token_record(db, user.id)
    db.commit()

    token = create_access_token(subject=user.id, role=primary_role)
    set_auth_cookies(response, raw_refresh_token)

    return Token(
        access_token=token,
        token_type="bearer",
        role=primary_role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        refresh_token=raw_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh")
def refresh_token_endpoint(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Rotates a refresh token strictly single-use.
    Detects token reuse: if a previously revoked token is presented, the entire
    token family is invalidated immediately to protect against replay attacks.
    """
    # 1. CSRF Verification
    csrf_cookie = request.cookies.get("gobeyond_csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")
    if csrf_cookie and (not csrf_header or csrf_cookie != csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")

    # 2. Extract refresh token from cookie or header
    raw_token = request.cookies.get("gobeyond_refresh_token")
    if not raw_token:
        # Check authorization or custom header fallback
        auth_header = request.headers.get("X-Refresh-Token")
        if auth_header:
            raw_token = auth_header

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found.")

    token_h = hash_token(raw_token)
    now = datetime.datetime.now(datetime.timezone.utc)

    # 3. Query token record
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
    if not record:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    # 4. REUSE DETECTION: If already revoked, revoke entire family!
    if record.is_revoked:
        db.query(RefreshToken).filter(RefreshToken.family_id == record.family_id).update({
            RefreshToken.is_revoked: True,
            RefreshToken.revoked_at: now
        })
        db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All sessions in this family have been revoked. Please log in again."
        )

    # 5. Check Expiry
    rec_exp = record.expires_at.replace(tzinfo=datetime.timezone.utc) if record.expires_at.tzinfo is None else record.expires_at
    if now > rec_exp:
        record.is_revoked = True
        record.revoked_at = now
        db.commit()
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired. Please log in again.")

    # 6. Strictly single-use rotation: Mark presented token revoked
    record.is_revoked = True
    record.revoked_at = now

    # 7. Issue new token in the same family
    new_raw_token, _ = create_refresh_token_record(db, record.user_id, family_id=record.family_id)
    db.commit()

    # 8. User role resolution
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or not user.is_active or getattr(user, "account_status", "ACTIVE") != "ACTIVE":
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated or suspended.")

    roles = [r.name for r in user.roles]
    primary_role = "customer"
    for priority_role in ["super_admin", "partner_cinema", "partner_restaurant", "partner_event", "partner_sports", "customer"]:
        if priority_role in roles:
            primary_role = priority_role
            break

    new_access_token = create_access_token(subject=user.id, role=primary_role)
    set_auth_cookies(response, new_raw_token)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": primary_role,
        "user_id": user.id,
        "refresh_token": new_raw_token
    }


@router.post("/logout")
def logout_endpoint(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revokes the current session's refresh token and clears all authentication cookies."""
    raw_token = request.cookies.get("gobeyond_refresh_token") or request.headers.get("X-Refresh-Token")
    if raw_token:
        token_h = hash_token(raw_token)
        record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
        if record:
            record.is_revoked = True
            record.revoked_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()

    clear_auth_cookies(response)
    return {"success": True, "message": "Successfully logged out from current session."}


@router.post("/logout-all")
def logout_all_sessions(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revokes ALL refresh tokens for the authenticated user across all devices/sessions.
    Clears local auth cookies.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    revoked_count = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False
    ).update({
        RefreshToken.is_revoked: True,
        RefreshToken.revoked_at: now
    })

    db.add(AuditLog(
        user_id=current_user.id,
        action="LOGOUT_ALL_SESSIONS",
        resource_type="USER",
        resource_id=str(current_user.id),
        details={"revoked_token_count": revoked_count}
    ))
    db.commit()

    clear_auth_cookies(response)
    return {
        "success": True,
        "message": f"Successfully logged out of all active sessions. ({revoked_count} session(s) terminated)."
    }


@router.post("/deactivate")
def deactivate_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Account deletion / deactivation workflow:
    - Sets is_active = False and account_status = 'DEACTIVATED'.
    - Revokes all active refresh tokens for the user.
    - Clears all session authentication cookies.
    - Creates an immutable audit log entry.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    current_user.is_active = False
    current_user.account_status = "DEACTIVATED"

    # Revoke all active tokens
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False
    ).update({
        RefreshToken.is_revoked: True,
        RefreshToken.revoked_at: now
    })

    db.add(AuditLog(
        user_id=current_user.id,
        action="ACCOUNT_DEACTIVATED",
        resource_type="USER",
        resource_id=str(current_user.id),
        details={"email": current_user.email, "deactivated_at": str(now)}
    ))
    db.commit()

    clear_auth_cookies(response)
    return {
        "success": True,
        "message": "Your account has been deactivated. All active sessions have been terminated."
    }


@router.post("/request-otp", dependencies=[Depends(otp_rate_limiter)])
def request_otp(req: OTPRequest):
    """
    Dispatches a 6-digit OTP using the Redis-backed OTPService.
    Expires in 300 seconds with a 3-attempt limit.
    In development sandbox mode, clearly labels test code with a developer notice.
    In production, fails safe with 503 if Redis OTP backend is unavailable.
    """
    try:
        return otp_service.send_otp(phone=req.phone, purpose=req.purpose)
    except RuntimeError as e:
        if settings.ENVIRONMENT in ["production", "prod"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OTP delivery service is temporarily unavailable. Please try again later."
            )
        raise


@router.post("/verify-otp", response_model=Token, dependencies=[Depends(otp_rate_limiter)])
def verify_otp(req: OTPVerifyRequest, response: Response, db: Session = Depends(get_db)):
    is_valid, msg = otp_service.verify_otp(phone=req.phone, otp=req.otp, purpose=req.purpose)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    # Find or auto-create customer for phone login
    clean_phone = req.phone.strip().replace(" ", "").replace("-", "")
    user = db.query(User).filter(User.phone == clean_phone).first()
    if not user:
        # Create standard customer
        role_record = db.query(Role).filter(Role.name == "customer").first()
        user = User(
            email=f"{clean_phone}@mobile.gobeyond.internal",
            phone=clean_phone,
            full_name=f"User {clean_phone[-4:]}",
            hashed_password=get_password_hash("GoBeyondOTPDefaultPass@123"),
            is_active=True,
            is_verified=True,
            account_status="ACTIVE"
        )
        if role_record:
            user.roles.append(role_record)
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id))
        db.commit()
    else:
        if not user.is_active or getattr(user, "account_status", "ACTIVE") != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is deactivated or suspended. Contact support."
            )
        user.is_verified = True
        db.commit()

    roles = [r.name for r in user.roles]
    primary_role = "customer"
    for priority_role in ["super_admin", "partner_cinema", "partner_restaurant", "partner_event", "partner_sports", "customer"]:
        if priority_role in roles:
            primary_role = priority_role
            break

    # Issue refresh token record
    raw_refresh_token, _ = create_refresh_token_record(db, user.id)
    db.commit()

    token = create_access_token(subject=user.id, role=primary_role)
    set_auth_cookies(response, raw_refresh_token)

    return Token(
        access_token=token,
        token_type="bearer",
        role=primary_role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        refresh_token=raw_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/forgot-password", dependencies=[Depends(password_reset_rate_limiter)])
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    search = req.email_or_phone.strip().lower()
    clean_phone = req.email_or_phone.strip().replace(" ", "").replace("-", "")
    user = db.query(User).filter(
        (User.email == search) | (User.phone == clean_phone)
    ).first()

    if not user:
        # Generic response to prevent user enumeration
        return {
            "message": "If an account matches those details, a reset code has been dispatched.",
            "is_sandbox": getattr(settings, "OTP_SANDBOX_MODE", True)
        }

    return otp_service.send_otp(phone=user.phone, purpose="password_reset")


@router.post("/reset-password", dependencies=[Depends(password_reset_rate_limiter)])
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    search = req.email_or_phone.strip().lower()
    clean_phone = req.email_or_phone.strip().replace(" ", "").replace("-", "")
    user = db.query(User).filter(
        (User.email == search) | (User.phone == clean_phone)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found."
        )

    is_valid, msg = otp_service.verify_otp(phone=user.phone, otp=req.otp, purpose="password_reset")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    user.hashed_password = get_password_hash(req.new_password)
    revoked_count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False
    ).update({"is_revoked": True}, synchronize_session=False)
    db.add(AuditLog(
        user_id=user.id,
        action="PASSWORD_RESET_REVOKED_SESSIONS",
        resource_type="USER",
        resource_id=str(user.id),
        details={"revoked_refresh_tokens": revoked_count}
    ))
    db.commit()

    return {"success": True, "message": "Password updated successfully. You may now log in with your new credentials."}


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = [r.name for r in current_user.roles]
    profile = current_user.profile
    city_name = profile.city.name if profile and profile.city else None
    city_id = profile.city_id if profile else None
    locality_name = profile.locality.name if profile and profile.locality else None
    locality_id = profile.locality_id if profile else None

    # Check partner link
    partner = db.query(Partner).filter(Partner.user_id == current_user.id).first()
    partner_id = partner.id if partner else None
    partner_type = partner.partner_type if partner else None

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        account_status=getattr(current_user, "account_status", "ACTIVE"),
        roles=roles,
        avatar_url=profile.avatar_url if profile else None,
        city_name=city_name,
        city_id=city_id,
        locality_name=locality_name,
        locality_id=locality_id,
        preferred_language=profile.preferred_language if profile else "English",
        bio=profile.bio if profile else None,
        partner_id=partner_id,
        partner_type=partner_type
    )


@router.put("/me", response_model=UserProfileResponse)
def update_me(
    req: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.full_name and req.full_name.strip():
        current_user.full_name = req.full_name.strip()

    profile = current_user.profile
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        db.flush()

    if req.preferred_language is not None:
        profile.preferred_language = req.preferred_language
    if req.avatar_url is not None:
        profile.avatar_url = req.avatar_url
    if req.bio is not None:
        profile.bio = req.bio
    if req.emergency_phone is not None:
        profile.emergency_phone = req.emergency_phone
    if req.city_id is not None:
        profile.city_id = req.city_id
    if "locality_id" in req.model_fields_set:
        if req.locality_id is None:
            profile.locality_id = None
        else:
            loc = db.query(Location).filter(
                Location.id == req.locality_id,
                Location.type == "LOCALITY",
                Location.is_active == True
            ).first()
            if not loc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Selected locality does not exist or is inactive."
                )
            profile.locality_id = loc.id
            if loc.parent_id:
                profile.city_id = loc.parent_id

    db.commit()
    db.refresh(current_user)
    return get_me(current_user=current_user, db=db)
