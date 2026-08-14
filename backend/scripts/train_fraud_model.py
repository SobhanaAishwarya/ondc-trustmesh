"""Train the fraud-detection model and save the artifact backend/app/ml
loads at runtime.

Usage:
    python scripts/train_fraud_model.py [--n 6000] [--seed 42]

Writes:
    datasets/synthetic_fraud_transactions.csv   (the training data, for
                                                  inspection/reproducibility)
    trained_models/fraud_model.joblib           (the artifact app/ml/model.py
                                                  loads — see get_fraud_model())
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import REPO_ROOT
from app.ml.model import save, train
from app.ml.synthetic_data import generate_synthetic_transactions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Generating {args.n} synthetic transactions (seed={args.seed})...")
    df = generate_synthetic_transactions(n=args.n, seed=args.seed)

    datasets_dir = REPO_ROOT / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = datasets_dir / "synthetic_fraud_transactions.csv"
    df.to_csv(dataset_path, index=False)
    print(f"Wrote training data to {dataset_path}")

    print("Training RandomForest fraud classifier...")
    model = train(df, seed=args.seed)

    model_path = REPO_ROOT / "trained_models" / "fraud_model.joblib"
    save(model, model_path)
    print(f"Saved model artifact to {model_path}")

    m = model.metrics
    print("\n--- Evaluation (held-out test split) ---")
    print(f"  accuracy:  {m['accuracy']:.4f}")
    print(f"  precision: {m['precision']:.4f}")
    print(f"  recall:    {m['recall']:.4f}")
    print(f"  f1:        {m['f1']:.4f}")
    print(f"  roc_auc:   {m['roc_auc']:.4f}")
    print(f"  fraud rate in data: {m['fraud_rate']:.4f}")
    print(f"  train/test rows: {m['n_train']}/{m['n_test']}")
    print(f"  confusion matrix [[TN, FP], [FN, TP]]: {m['confusion_matrix']}")

    print("\n--- Global feature importances ---")
    for feature, importance in sorted(model.feature_importances.items(), key=lambda kv: -kv[1]):
        print(f"  {feature:<24} {importance:.4f}")

    target_accuracy = 0.85
    status = "MEETS" if m["accuracy"] >= target_accuracy else "BELOW"
    print(f"\nKPI target (fraud detection accuracy > {target_accuracy:.0%}): {status} ({m['accuracy']:.2%})")


if __name__ == "__main__":
    main()
