from app.services.trust_service import TrustMetrics, compute_trust_score

NEUTRAL = TrustMetrics(
    transaction_success_rate=1.0,
    delivery_success_rate=1.0,
    avg_customer_rating=3.0,
    complaint_ratio=0.0,
    dispute_count=0,
    fraud_probability=0.0,
    refund_ratio=0.0,
    late_delivery_ratio=0.0,
    order_completion_rate=1.0,
    seller_age_days=0,
)


def _with(**overrides) -> TrustMetrics:
    return TrustMetrics(**{**NEUTRAL.__dict__, **overrides})


def test_neutral_metrics_score_is_in_range():
    score = compute_trust_score(NEUTRAL)
    assert 0.0 <= score <= 100.0


def test_score_is_clamped_at_zero_for_a_worst_case_seller():
    worst = _with(
        transaction_success_rate=0.0,
        delivery_success_rate=0.0,
        avg_customer_rating=1.0,
        complaint_ratio=1.0,
        dispute_count=50,
        fraud_probability=1.0,
        refund_ratio=1.0,
        late_delivery_ratio=1.0,
        order_completion_rate=0.0,
    )
    assert compute_trust_score(worst) == 0.0


def test_score_is_clamped_at_hundred_for_a_best_case_seller():
    best = _with(avg_customer_rating=5.0, seller_age_days=1000)
    assert compute_trust_score(best) == 100.0


def test_higher_fraud_probability_lowers_score():
    low_fraud = _with(fraud_probability=0.05)
    high_fraud = _with(fraud_probability=0.9)
    assert compute_trust_score(low_fraud) > compute_trust_score(high_fraud)


def test_more_disputes_lowers_score():
    few = _with(dispute_count=1)
    many = _with(dispute_count=8)
    assert compute_trust_score(few) > compute_trust_score(many)


def test_seller_age_gives_a_nonnegative_bonus():
    new_seller = _with(seller_age_days=0)
    old_seller = _with(seller_age_days=400)
    assert compute_trust_score(old_seller) >= compute_trust_score(new_seller)
