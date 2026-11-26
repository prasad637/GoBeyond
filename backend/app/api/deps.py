from typing import Generator, Optional, List, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.partner import Partner

security_scheme = HTTPBearer(auto_error=False)

ROLE_ALIASES = {
    "customer": {"customer", "CUSTOMER"},
    "partner_restaurant": {"partner_restaurant", "RESTAURANT_PARTNER", "restaurant_partner"},
    "partner_cinema": {"partner_cinema", "CINEMA_PARTNER", "cinema_partner"},
    "partner_event": {"partner_event", "EVENT_ORGANIZER", "event_organizer", "partner_events"},
    "partner_sports": {"partner_sports", "SPORTS_PARTNER", "sports_partner", "partner_activities"},
    "super_admin": {"super_admin", "SUPER_ADMIN", "admin", "ADMIN"},
}


def _expand_roles(roles: List[str]) -> Set[str]:
    expanded = set()
    for r in roles:
        expanded.add(r)
        expanded.add(r.lower())
        expanded.add(r.upper())
        for canonical, aliases in ROLE_ALIASES.items():
            if r in aliases or r.lower() == canonical:
                expanded.update(aliases)
                expanded.add(canonical)
    return expanded


def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Bearer token not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.credentials
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject identity.",
        )
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    if not user.is_active or getattr(user, "account_status", "ACTIVE") in ["DEACTIVATED", "SUSPENDED"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is deactivated or suspended. Please contact support.",
        )
    return user


def get_optional_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Resolves authenticated user if valid token present; returns None for guests."""
    if not auth_header:
        return None
    try:
        token = auth_header.credentials
        payload = decode_access_token(token)
        if not payload or not payload.get("sub"):
            return None
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active or getattr(user, "account_status", "ACTIVE") in ["DEACTIVATED", "SUSPENDED"]:
            return None
        return user
    except Exception:
        return None


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user


def require_roles(allowed_roles: List[str]):
    """
    Enforces RBAC on the backend with alias normalization.
    Super Admin always passes authorization.
    """
    allowed_set = _expand_roles(allowed_roles)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {r.name for r in current_user.roles}
        user_role_names_expanded = _expand_roles(list(user_role_names))

        if "super_admin" in user_role_names_expanded or "SUPER_ADMIN" in user_role_names_expanded:
            return current_user  # Super admin bypasses role checks

        if not user_role_names_expanded.intersection(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {allowed_roles}",
            )
        return current_user
    return role_checker


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Convenience dependency for super admin operations."""
    user_roles = [r.name.lower() for r in current_user.roles]
    if "super_admin" not in user_roles and "admin" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges required.",
        )
    return current_user


def get_current_partner(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Partner:
    """
    Extracts and validates the partner profile associated with the authenticated user.
    Enforces partner data isolation at the boundary.
    """
    partner = db.query(Partner).filter(Partner.user_id == current_user.id).first()
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted. No partner profile associated with this account.",
        )
    return partner


def get_current_approved_partner(
    current_partner: Partner = Depends(get_current_partner)
) -> Partner:
    """
    Requires that the authenticated partner has been verified/approved by Super Admin.
    Pending, rejected or suspended partners cannot access live operational functions.
    """
    if current_partner.status not in ["APPROVED", "ACTIVE"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Partner account is pending approval. Operational access is not permitted."
        )
    return current_partner

