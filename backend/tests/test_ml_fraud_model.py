import pytest

from app.ml.features import ALL_FEATURES
from app.ml.model import load, save, train
from app.ml.synthetic_data import generate_synthetic_transactions

LOW_RISK_SAMPLE = {
    "transaction_amount": 300.0,
    "buyer_account_age_days": 800.0,
    "seller_trust_score": 90.0,
    "num_previous_disputes": 0.0,
    "velocity_1h": 0.0,
    "seller_rating": 4.8,
    "is_new_seller": 0.0,
    "payment_method": "upi",
    "category": "Books",
}
HIGH_RISK_SAMPLE = {
    "transaction_amount": 5000.0,
    "buyer_account_age_days": 3.0,
    "seller_trust_score": 22.0,
    "num_previous_disputes": 4.0,
    "velocity_1h": 6.0,
    "seller_rating": 1.5,
    "is_new_seller": 1.0,
    "payment_method": "cod",
    "category": "Electronics",
}


@pytest.fixture(scope="module")
def trained_model():
    df = generate_synthetic_transactions(n=3000, seed=1)
    return train(df, seed=1)


def test_training_pipeline_produces_reasonable_accuracy(trained_model):
    # The full n=6000 run (scripts/train_fraud_model.py) measured ~90% on a
    # held-out split; this is a smaller/faster run so the floor is looser —
    # it's a regression guard, not a re-verification of the KPI number.
    assert trained_model.metrics["accuracy"] > 0.80
    assert 0.0 <= trained_model.metrics["roc_auc"] <= 1.0


def test_feature_importances_cover_every_feature(trained_model):
    assert set(trained_model.feature_importances) == set(ALL_FEATURES)
    assert all(v >= 0 for v in trained_model.feature_importances.values())


def test_predict_proba_returns_a_probability(trained_model):
    probability = trained_model.predict_proba(LOW_RISK_SAMPLE)
    assert 0.0 <= probability <= 1.0


def test_high_risk_profile_scores_higher_than_low_risk(trained_model):
    assert trained_model.predict_proba(HIGH_RISK_SAMPLE) > trained_model.predict_proba(LOW_RISK_SAMPLE)


def test_save_and_load_round_trip(trained_model, tmp_path):
    path = tmp_path / "model.joblib"
    save(trained_model, path)
    loaded = load(path)
    # n_jobs=-1 averages tree votes across threads, so predict_proba isn't
    # bit-exact between calls even without serialization in between —
    # approx equality is the correct check here, not identity.
    assert loaded.predict_proba(LOW_RISK_SAMPLE) == pytest.approx(trained_model.predict_proba(LOW_RISK_SAMPLE))
