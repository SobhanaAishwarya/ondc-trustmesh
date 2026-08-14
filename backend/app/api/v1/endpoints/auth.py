"""Registration, login, and identity endpoints for all three roles.

Buyers and sellers self-register here. Admins deliberately have no public
registration endpoint — letting anyone POST their way to an admin role
would be a privilege-escalation hole — so the first admin account is
created via `scripts/create_admin.py` (see backend/README.md), and further
admins would be provisioned by an existing admin through a future
admin-management endpoint.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.cache import blocklist_add, blocklist_contains
from app.core.limiter import limiter
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.buyer import Buyer
from app.models.seller import Seller
from app.models.user import User, UserRole
from app.schemas.user import (
    BuyerRegisterRequest,
    LoginRequest,
    MeResponse,
    ProfileUpdate,
    RefreshRequest,
    SellerRegisterRequest,
    TokenResponse,
)
from app.services.blockchain_service import register_buyer_onchain, register_seller_onchain

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/buyer", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register_buyer(request: Request, payload: BuyerRegisterRequest, db: DbSession) -> TokenResponse:
    _ensure_email_available(db, payload.email)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole.buyer,
    )
    db.add(user)
    db.flush()  # assigns user.id before we reference it below

    db.add(Buyer(user_id=user.id, preferred_categories=payload.preferred_categories, city=payload.city))
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/register/seller", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register_seller(request: Request, payload: SellerRegisterRequest, db: DbSession) -> TokenResponse:
    _ensure_email_available(db, payload.email)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=UserRole.seller,
    )
    db.add(user)
    db.flush()

    db.add(
        Seller(
            user_id=user.id,
            business_name=payload.business_name,
            gstin=payload.gstin,
            city=payload.city,
            delivery_radius_km=payload.delivery_radius_km,
        )
    )
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _issue_token(user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh_access_token(request: Request, payload: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    if blocklist_contains(token_payload.jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")

    user = db.get(User, uuid.UUID(token_payload.sub))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # Revoke the just-used refresh token immediately rather than letting it
    # keep working until its own expiry — true rotation, not just a fresh
    # access token alongside a still-valid old refresh token. No-ops if
    # Redis isn't reachable (see app/core/cache.py).
    blocklist_add(token_payload.jti, _seconds_until(token_payload.exp))
    return _issue_token(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest) -> None:
    """Revokes a refresh token on demand (e.g. user-initiated sign-out on
    a device) rather than waiting for it to either be rotated via
    `/auth/refresh` or expire naturally. Silently succeeds for an
    already-invalid/expired token — logging out doesn't need to prove the
    token was ever valid."""
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
    except InvalidTokenError:
        return
    blocklist_add(token_payload.jti, _seconds_until(token_payload.exp))


@router.get("/me", response_model=MeResponse)
def read_me(current_user: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(current_user)


@router.patch("/me", response_model=MeResponse)
def update_me(payload: ProfileUpdate, current_user: CurrentUser, db: DbSession) -> MeResponse:
    fields = payload.model_dump(exclude_unset=True)

    if "full_name" in fields:
        current_user.full_name = fields["full_name"]
    if "phone" in fields:
        current_user.phone = fields["phone"]

    if current_user.role == UserRole.buyer:
        buyer = db.scalar(select(Buyer).where(Buyer.user_id == current_user.id))
        if "wallet_address" in fields:
            buyer.wallet_address = fields["wallet_address"]
        if "preferred_categories" in fields:
            buyer.preferred_categories = fields["preferred_categories"]
        if "city" in fields:
            buyer.city = fields["city"]
        if "wallet_address" in fields:
            register_buyer_onchain(db, buyer)  # no-ops if the chain isn't enabled/reachable
    elif current_user.role == UserRole.seller:
        seller = db.scalar(select(Seller).where(Seller.user_id == current_user.id))
        if "wallet_address" in fields:
            seller.wallet_address = fields["wallet_address"]
        if "business_name" in fields:
            seller.business_name = fields["business_name"]
        if "gstin" in fields:
            seller.gstin = fields["gstin"]
        if "city" in fields:
            seller.city = fields["city"]
        if "delivery_radius_km" in fields:
            seller.delivery_radius_km = fields["delivery_radius_km"]
        if "wallet_address" in fields:
            register_seller_onchain(db, seller)  # no-ops if the chain isn't enabled/reachable

    db.commit()
    db.refresh(current_user)
    return MeResponse.model_validate(current_user)


def _seconds_until(exp: datetime) -> float:
    return (exp - datetime.now(timezone.utc)).total_seconds()


def _ensure_email_available(db: DbSession, email: str) -> None:
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")


def _issue_token(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        role=user.role,
        user_id=user.id,
    )
