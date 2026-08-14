"""Fraud-detection model: training, persistence, and a lazily-loaded
process-wide singleton that the live scoring service (services/fraud_service.py)
calls into.

Same algorithm family as the Streamlit prototype's ml/fraud_model.py
(a RandomForest over a StandardScaler+OneHotEncoder ColumnTransformer,
class_weight="balanced" since fraud is rare) — reused because it's already
proven to hit the >85% accuracy target, just retrained here on the reduced,
real-time-safe feature set from features.py.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.config import get_settings
from app.ml.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from app.ml.synthetic_data import generate_synthetic_transactions

MODEL_NAME = "random_forest"
MODEL_VERSION = "1.0.0"


@dataclass
class TrainedFraudModel:
    pipeline: Pipeline
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    feature_importances: dict[str, float]
    metrics: dict

    def predict_proba(self, features: dict) -> float:
        row = pd.DataFrame([features])[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        return float(self.pipeline.predict_proba(row)[0, 1])


def train(df: pd.DataFrame, test_size: float = 0.25, seed: int = 42) -> TrainedFraudModel:
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df["is_fraud"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )

    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    pipeline = Pipeline(
        [
            ("prep", preprocessor),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=10,
                    min_samples_leaf=3,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "fraud_rate": float(y.mean()),
    }

    feature_means = {f: float(X_train[f].mean()) for f in NUMERIC_FEATURES}
    feature_stds = {f: float(X_train[f].std() or 1.0) for f in NUMERIC_FEATURES}
    feature_importances = _raw_feature_importances(pipeline)

    return TrainedFraudModel(pipeline, feature_means, feature_stds, feature_importances, metrics)


def _raw_feature_importances(pipeline: Pipeline) -> dict[str, float]:
    """Collapses one-hot-encoded categorical importances back onto their
    original column name (summed) so explainability output says
    "payment_method" rather than "payment_method_cod"."""
    prep = pipeline.named_steps["prep"]
    clf = pipeline.named_steps["clf"]
    cat_names = list(prep.named_transformers_["cat"].get_feature_names_out(CATEGORICAL_FEATURES))
    all_names = NUMERIC_FEATURES + cat_names

    raw_importances = dict.fromkeys(NUMERIC_FEATURES + CATEGORICAL_FEATURES, 0.0)
    for name, importance in zip(all_names, clf.feature_importances_):
        if name in NUMERIC_FEATURES:
            raw_importances[name] += float(importance)
        else:
            base = next(c for c in CATEGORICAL_FEATURES if name.startswith(c + "_"))
            raw_importances[base] += float(importance)
    return raw_importances


def save(model: TrainedFraudModel, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load(path: str | Path) -> TrainedFraudModel:
    return joblib.load(Path(path))


_lock = threading.Lock()
_cached_model: TrainedFraudModel | None = None


def get_fraud_model() -> TrainedFraudModel:
    """Process-wide singleton. Loads the pre-trained artifact if
    `scripts/train_fraud_model.py` has been run; otherwise trains a smaller
    model on the fly (fresh checkout, CI, tests) so the API never hard-fails
    for lack of a file on disk."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    with _lock:
        if _cached_model is not None:
            return _cached_model

        path = Path(get_settings().fraud_model_path)
        if path.exists():
            _cached_model = load(path)
        else:
            _cached_model = train(generate_synthetic_transactions(n=2000))
        return _cached_model


def reset_cached_model() -> None:
    """Test hook: forces the next get_fraud_model() call to reload/retrain."""
    global _cached_model
    _cached_model = None
