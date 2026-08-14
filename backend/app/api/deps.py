"""Shared FastAPI dependencies: DB session access, current-user resolution,
and role-based access guards used by every protected endpoint."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.buyer import Buyer
from app.models.seller import Seller
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    user = db.get(User, uuid.UUID(payload.sub))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """Dependency factory: `Depends(require_role(UserRole.admin))` etc."""

    def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions for this action")
        return user

    return _check


def get_current_buyer(
    user: Annotated[User, Depends(require_role(UserRole.buyer))],
    db: DbSession,
) -> Buyer:
    """Resolves the buyer profile row for the authenticated user. Registration
    always creates one alongside the user, so a missing row means the two got
    out of sync — a server bug, not a client error."""
    buyer = db.scalar(select(Buyer).where(Buyer.user_id == user.id))
    if buyer is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Buyer profile missing for buyer user")
    return buyer


def get_current_seller(
    user: Annotated[User, Depends(require_role(UserRole.seller))],
    db: DbSession,
) -> Seller:
    seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Seller profile missing for seller user")
    return seller


CurrentBuyer = Annotated[Buyer, Depends(get_current_buyer)]
CurrentSeller = Annotated[Seller, Depends(get_current_seller)]
CurrentAdmin = Annotated[User, Depends(require_role(UserRole.admin))]
