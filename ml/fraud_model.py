"""AI fraud detection for ONDC transactions — a Random Forest classifier
over transaction, buyer, and blockchain-derived seller-trust features."""

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = [
    "transaction_amount", "buyer_account_age_days", "seller_trust_score",
    "delivery_time_hours", "num_previous_disputes", "velocity_1h",
    "distance_km", "seller_rating", "is_new_seller",
]
CATEGORICAL = ["payment_method", "category"]


def train_fraud_model(df, test_size=0.25, seed=42):
    X = df[NUMERIC + CATEGORICAL]
    y = df["is_fraud"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )

    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ]
    )

    model = Pipeline(
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
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba),
        "confusion_matrix": confusion_matrix(y_test, y_pred),
        "fpr_tpr": roc_curve(y_test, y_proba),
        "feature_importances": _feature_importances(model),
        "n_test": len(y_test),
    }
    return model, metrics


def _feature_importances(model):
    prep = model.named_steps["prep"]
    clf = model.named_steps["clf"]
    cat_names = list(prep.named_transformers_["cat"].get_feature_names_out(CATEGORICAL))
    names = NUMERIC + cat_names
    return sorted(zip(names, clf.feature_importances_), key=lambda x: -x[1])
