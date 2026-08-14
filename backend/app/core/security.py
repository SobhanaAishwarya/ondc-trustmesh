"""Password hashing and JWT issuance/verification.

Uses `bcrypt` directly rather than passlib — passlib's bcrypt backend breaks
on bcrypt>=4.1 (it probes a removed `__about__.__version__` attribute), and
the direct API is only a few lines anyway.

Every token (access and refresh) carries a unique `jti`. Refresh-token
revocation (`app/core/cache.blocklist_add`/`blocklist_contains`, wired up
in `app/api/v1/endpoints/auth.py`'s `/auth/refresh` and `/auth/logout`)
uses it as the blocklist key — `/auth/refresh` rotates tokens *and*
revokes the just-used refresh token immediately, closing the replay
window entirely rather than just limiting it. Access tokens aren't
checked against the blocklist on every request (that would put Redis on
the hot path of every authenticated call for a token that's already
short-lived by design) — only the refresh flow enforces revocation.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
import jwt
from pydantic import BaseModel

from app.core.config import get_settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str
    role: str
    type: str
    jti: str
    exp: datetime


class InvalidTokenError(Exception):
    pass


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: UUID, role: str) -> str:
    settings = get_settings()
    return _encode(user_id, role, TOKEN_TYPE_ACCESS, timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: UUID, role: str) -> str:
    settings = get_settings()
    return _encode(user_id, role, TOKEN_TYPE_REFRESH, timedelta(days=settings.refresh_token_expire_days))


def decode_access_token(token: str) -> TokenPayload:
    return _decode(token, TOKEN_TYPE_ACCESS)


def decode_refresh_token(token: str) -> TokenPayload:
    return _decode(token, TOKEN_TYPE_REFRESH)


def _encode(user_id: UUID, role: str, token_type: str, ttl: timedelta) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + ttl
    payload = {"sub": str(user_id), "role": role, "type": token_type, "jti": str(uuid4()), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode(token: str, expected_type: str) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Not a {expected_type} token")

    return TokenPayload.model_validate(payload)
