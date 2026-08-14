"""Recommendation endpoints: a ranked list for the current buyer (logging
an impression per item for CTR evaluation), click-through tracking, and an
algorithm-level CTR report for admins.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAdmin, CurrentBuyer, DbSession
from app.models.recommendation import Recommendation
from app.schemas.product import ProductRead
from app.schemas.recommendation import CTRReport, RecommendationItemRead
from app.services.recommendation_service import compute_ctr, get_recommendations, record_impressions

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationItemRead])
def list_recommendations(buyer: CurrentBuyer, db: DbSession, top_k: int = 10) -> list[RecommendationItemRead]:
    top_k = max(1, min(top_k, 50))
    scored = get_recommendations(db, buyer, top_k=top_k)
    records = record_impressions(db, buyer, scored)
    db.commit()

    results = []
    for rec, item in zip(records, scored):
        db.refresh(rec)
        results.append(
            RecommendationItemRead(
                id=rec.id,
                product=ProductRead.model_validate(item.product),
                algorithm=rec.algorithm,
                score=rec.score,
                rank=rec.rank,
                was_clicked=rec.was_clicked,
                was_purchased=rec.was_purchased,
                shown_at=rec.shown_at,
                distance_km=item.distance_km,
                estimated_delivery_days=item.estimated_delivery_days,
            )
        )
    return results


@router.post("/{recommendation_id}/click", status_code=status.HTTP_204_NO_CONTENT)
def record_click(recommendation_id: uuid.UUID, buyer: CurrentBuyer, db: DbSession) -> None:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None or rec.buyer_id != buyer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")

    if not rec.was_clicked:
        rec.was_clicked = True
        rec.clicked_at = datetime.now(timezone.utc)
        db.commit()


@router.get("/ctr", response_model=CTRReport)
def ctr_report(admin: CurrentAdmin, db: DbSession, algorithm: str | None = None) -> CTRReport:
    return CTRReport(**compute_ctr(db, algorithm=algorithm))
