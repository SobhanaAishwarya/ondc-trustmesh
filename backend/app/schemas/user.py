import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.geo import CITY_NAMES
from app.models.user import UserRole

# Format only (0x + 40 hex chars) — not full EIP-55 checksum validation,
# since an all-lowercase or all-uppercase address is legitimately valid
# too and most wallets don't enforce mixed-case checksums on copy/paste.
# Catches the actual failure mode that mattered in practice: a malformed
# address (wrong length, non-hex characters — e.g. a transcription typo)
# was silently accepted here, then failed deep inside
# blockchain_service.register_seller_onchain's best-effort try/except
# with zero feedback to the caller — `is_onchain_registered` just stayed
# `false` with no explanation. Reject it at the door instead.
WALLET_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _validate_city(value: str | None) -> str | None:
    if value is not None and value not in CITY_NAMES:
        raise ValueError(f"city must be one of {CITY_NAMES}")
    return value


def _validate_wallet_address(value: str | None) -> str | None:
    if value is not None and not WALLET_ADDRESS_PATTERN.match(value):
        raise ValueError("wallet_address must be a 0x-prefixed 40-character hex string")
    return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime


class BuyerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wallet_address: str | None
    wallet_verified: bool
    price_sensitivity: Decimal
    preferred_categories: list[str]
    city: str | None
    account_age_days: int
    is_onchain_registered: bool


class SellerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_name: str
    wallet_address: str | None
    wallet_verified: bool
    gstin: str | None
    city: str | None
    delivery_radius_km: int
    seller_age_days: int
    current_trust_score: Decimal
    is_onchain_registered: bool


class MeResponse(UserRead):
    buyer: BuyerProfileRead | None = None
    seller: SellerProfileRead | None = None


class BuyerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    preferred_categories: list[str] = Field(default_factory=list)
    city: str | None = None

    _validate_city = field_validator("city")(_validate_city)


class SellerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    business_name: str = Field(min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    city: str | None = None
    delivery_radius_km: int = Field(default=50, ge=1, le=5000)

    _validate_city = field_validator("city")(_validate_city)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: uuid.UUID


class RefreshRequest(BaseModel):
    refresh_token: str


class WalletNonceRequest(BaseModel):
    address: str = Field(pattern=WALLET_ADDRESS_PATTERN.pattern)


class WalletNonceResponse(BaseModel):
    message: str


class WalletVerifyRequest(BaseModel):
    """address + the signature MetaMask (or any EIP-1191 wallet) produced
    by signing the exact `message` a prior POST /auth/wallet/nonce call
    returned."""

    address: str = Field(pattern=WALLET_ADDRESS_PATTERN.pattern)
    signature: str = Field(min_length=1)


class ProfileUpdate(BaseModel):
    """Fields only apply to the caller's own role; irrelevant ones (e.g. a
    buyer sending business_name) are silently ignored rather than erroring
    — same "own profile, partial update" contract as PATCH /products/{id}."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    wallet_address: str | None = Field(default=None, max_length=42)
    # buyer or seller
    city: str | None = None
    # buyer-only
    preferred_categories: list[str] | None = None
    # seller-only
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    delivery_radius_km: int | None = Field(default=None, ge=1, le=5000)

    _validate_city = field_validator("city")(_validate_city)
    _validate_wallet_address = field_validator("wallet_address")(_validate_wallet_address)
