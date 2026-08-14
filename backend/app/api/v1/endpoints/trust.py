"""Trust score endpoints: public current-score lookup (buyers see this
before purchasing), history for dashboards, and a manual recompute trigger.
Automatic recomputation also happens when an order is marked delivered and
when a review is posted (see orders.py / reviews.py) — this endpoint's
lazy-compute-on-first-read only covers a seller nobody has transacted with.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.cache import cache_get, cache_set
from app.models.seller import Seller
from app.models.trust_score import TrustScore
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.trust import OnchainTrustRead, TrustScoreRead
from app.services.blockchain_service import get_onchain_score, is_enabled
from app.services.trust_service import recompute_trust_score, trust_score_cache_key

router = APIRouter(prefix="/trust", tags=["trust"])

# Short TTL: this is a read-heavy, write-light value (recomputed on
# delivery/review/dispute/admin-trigger, which also proactively evicts the
# key — see trust_service.recompute_trust_score) — the TTL is just a
# safety net against a stale entry outliving a code path that doesn't.
TRUST_SCORE_CACHE_TTL_SECONDS = 30


@router.get("/sellers/{seller_id}", response_model=TrustScoreRead)
def get_current_trust_score(seller_id: uuid.UUID, db: DbSession) -> TrustScoreRead:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller not found")

    cache_key = trust_score_cache_key(seller_id)
    cached = cache_get(cache_key)
    if cached is not None:
        return TrustScoreRead.model_validate_json(cached)

    latest = db.scalar(
        select(TrustScore).where(TrustScore.seller_id == seller_id).order_by(TrustScore.computed_at.desc())
    )
    if latest is None:
        latest = recompute_trust_score(db, seller)
        db.commit()
        db.refresh(latest)

    result = TrustScoreRead.model_validate(latest)
    cache_set(cache_key, result.model_dump_json(), TRUST_SCORE_CACHE_TTL_SECONDS)
    return result


@router.get("/sellers/{seller_id}/history", response_model=Page[TrustScoreRead])
def get_trust_score_history(
    seller_id: uuid.UUID, db: DbSession, limit: int = 20, offset: int = 0
) -> Page[TrustScoreRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    total = db.scalar(select(func.count()).select_from(TrustScore).where(TrustScore.seller_id == seller_id)) or 0
    rows = db.scalars(
        select(TrustScore)
        .where(TrustScore.seller_id == seller_id)
        .order_by(TrustScore.computed_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return Page(items=[TrustScoreRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/sellers/{seller_id}/recompute", response_model=TrustScoreRead, status_code=status.HTTP_201_CREATED)
def trigger_recompute(seller_id: uuid.UUID, user: CurrentUser, db: DbSession) -> TrustScoreRead:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller not found")

    is_self = user.role == UserRole.seller and seller.user_id == user.id
    if not (is_self or user.role == UserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to recompute this seller's trust score")

    trust_score = recompute_trust_score(db, seller)
    db.commit()
    db.refresh(trust_score)
    return TrustScoreRead.model_validate(trust_score)


@router.get("/sellers/{seller_id}/onchain", response_model=OnchainTrustRead)
def get_onchain_trust(seller_id: uuid.UUID, db: DbSession) -> OnchainTrustRead:
    """Reads the score straight from TrustScore.sol (the simpler
    event-delta model), separate from the multi-factor score above —
    the two are different models by design, see backend/README.md."""
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller not found")

    score = get_onchain_score(seller)
    return OnchainTrustRead(
        seller_id=seller.id,
        wallet_address=seller.wallet_address,
        is_onchain_registered=seller.is_onchain_registered,
        onchain_score=score,
        blockchain_enabled=is_enabled(),
    )
