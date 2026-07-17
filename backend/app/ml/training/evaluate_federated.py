"""
Federated vs Centralized Evaluation
--------------------------------------
Compares the global federated MLP against the centralized XGBoost baseline
on the same test set. This comparison IS the research contribution:
"federated MLP achieves X% of centralized accuracy without centralizing data."

Outputs to artifacts/metrics/:
  comparison_report.txt        — side-by-side metrics table
  federated_classification_report.txt
  federated_confusion_matrix.csv
  comparison_metrics.json      — machine-readable for charts/papers

Usage:
    cd backend
    PYTHONPATH=. python app/ml/training/evaluate_federated.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_test_set(feature_table_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load the held-out test set produced by pipeline.py."""
    test_path = feature_table_dir / "feature_table_test.parquet"
    if not test_path.exists():
        raise FileNotFoundError(
            f"Test parquet not found: {test_path}\n"
            "Run: PYTHONPATH=. python app/ml/features/pipeline.py --source csv"
        )
    from app.ml.features.windowing import FEATURE_COLUMNS
    test_df = pd.read_parquet(test_path)
    X = test_df[FEATURE_COLUMNS].values.astype(np.float32)
    y = test_df["label_idx"].values.astype(np.int32)
    return X, y


def evaluate_xgboost(X_test: np.ndarray, y_test: np.ndarray, baseline_dir: Path) -> dict | None:
    """Evaluate the saved XGBoost baseline."""
    model_path = baseline_dir / "xgboost_baseline.ubj"
    if not model_path.exists():
        logger.warning("XGBoost model not found at %s — skipping", model_path)
        return None
    import xgboost as xgb
    model = xgb.XGBClassifier()
    model.load_model(str(model_path))
    y_pred = model.predict(X_test)
    return _compute_metrics(y_test, y_pred, model_name="XGBoost (centralized)")


def evaluate_mlp(X_test: np.ndarray, y_test: np.ndarray, federated_dir: Path) -> dict | None:
    """Evaluate the global FL MLP."""
    weights_path = federated_dir / "global_mlp_weights.npz"
    if not weights_path.exists():
        logger.warning("Global MLP weights not found at %s — skipping", weights_path)
        return None

    import torch
    from app.services.federated_learning.local_model import MLPLocalModel

    model = MLPLocalModel.initial()
    data = np.load(str(weights_path))
    params = [data[k] for k in sorted(data.files)]
    model.set_parameters(params)

    X_t = torch.tensor(X_test, dtype=torch.float32)
    model.net.eval()
    with torch.no_grad():
        proba = model.net.predict_proba(X_t).numpy()
    y_pred = np.argmax(proba, axis=1)
    return _compute_metrics(y_test, y_pred, model_name="MLP (federated)")


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, model_name: str) -> dict:
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report, confusion_matrix
    )
    from app.ml.features.pipeline import IDX_TO_LABEL
    label_names = [IDX_TO_LABEL[i] for i in range(len(IDX_TO_LABEL))]
    return {
        "model": model_name,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "classification_report": classification_report(y_true, y_pred, target_names=label_names, digits=4),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def print_comparison(xgb_metrics: dict | None, mlp_metrics: dict | None) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("FedRouteAI — Centralized vs Federated Evaluation")
    lines.append("=" * 70)
    lines.append(f"{'Metric':<25} {'XGBoost (central)':>20} {'MLP (federated)':>20}")
    lines.append("-" * 70)

    for key in ["accuracy", "macro_f1", "weighted_f1"]:
        xgb_val = f"{xgb_metrics[key]:.4f}" if xgb_metrics else "N/A"
        mlp_val = f"{mlp_metrics[key]:.4f}" if mlp_metrics else "N/A"
        lines.append(f"  {key:<23} {xgb_val:>20} {mlp_val:>20}")

    lines.append("=" * 70)

    if mlp_metrics and xgb_metrics:
        ratio = mlp_metrics["macro_f1"] / max(xgb_metrics["macro_f1"], 1e-6)
        lines.append(f"\nFederated MLP achieves {ratio*100:.1f}% of centralized XGBoost macro F1")
        lines.append("(without centralizing any training data)\n")

    if mlp_metrics:
        lines.append("\nFederated MLP — Classification Report:")
        lines.append(mlp_metrics["classification_report"])

    return "\n".join(lines)


def run_evaluation(
    feature_table_dir: Path,
    baseline_dir: Path,
    federated_dir: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading test set from %s", feature_table_dir)
    X_test, y_test = load_test_set(feature_table_dir)
    logger.info("Test set: %d rows", len(X_test))

    xgb_metrics = evaluate_xgboost(X_test, y_test, baseline_dir)
    mlp_metrics = evaluate_mlp(X_test, y_test, federated_dir)

    report = print_comparison(xgb_metrics, mlp_metrics)
    print(report)
    (output_dir / "comparison_report.txt").write_text(report, encoding="utf-8")

    if mlp_metrics:
        (output_dir / "federated_classification_report.txt").write_text(
            mlp_metrics["classification_report"], encoding="utf-8"
        )
        from app.ml.features.pipeline import IDX_TO_LABEL
        label_names = [IDX_TO_LABEL[i] for i in range(len(IDX_TO_LABEL))]
        cm_df = pd.DataFrame(
            mlp_metrics["confusion_matrix"],
            index=label_names, columns=label_names,
        )
        cm_df.to_csv(output_dir / "federated_confusion_matrix.csv")

    summary = {
        "xgboost": {k: xgb_metrics[k] for k in ["accuracy", "macro_f1", "weighted_f1"]} if xgb_metrics else None,
        "mlp_federated": {k: mlp_metrics[k] for k in ["accuracy", "macro_f1", "weighted_f1"]} if mlp_metrics else None,
    }
    (output_dir / "comparison_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("Evaluation artifacts saved to %s", output_dir)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    parser = argparse.ArgumentParser(description="Compare federated MLP vs XGBoost baseline.")
    parser.add_argument("--feature-table-dir", default="app/ml/artifacts/feature_tables")
    parser.add_argument("--baseline-dir", default="app/ml/artifacts/baseline")
    parser.add_argument("--federated-dir", default="app/ml/artifacts/federated")
    parser.add_argument("--output-dir", default="app/ml/artifacts/metrics")
    args = parser.parse_args()

    run_evaluation(
        feature_table_dir=Path(args.feature_table_dir),
        baseline_dir=Path(args.baseline_dir),
        federated_dir=Path(args.federated_dir),
        output_dir=Path(args.output_dir),
    )
