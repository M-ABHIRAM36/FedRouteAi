"""
Centralized XGBoost Baseline Training
---------------------------------------
Trains an XGBoost classifier on the centralized (global) feature table and
produces a complete set of research artifacts. This is the sanity-check step
before any federated training: if XGBoost can't learn separable event types
centrally, there's a feature engineering problem — not a FL problem.

Outputs (all to app/ml/artifacts/baseline/):
  xgboost_baseline.ubj        — trained model (binary JSON format)
  classification_report.txt   — per-class precision / recall / F1 / support
  confusion_matrix.csv        — 8×8 matrix (true vs predicted)
  roc_auc.json                — per-class one-vs-rest AUC scores
  feature_importance.csv      — gain, weight, cover per feature (all 10)
  metrics.json                — summary (accuracy, macro F1, weighted F1)
  training_log.txt            — XGBoost eval log per round

Usage:
    cd backend
    PYTHONPATH=. python app/ml/training/train_baseline_xgboost.py
    PYTHONPATH=. python app/ml/training/train_baseline_xgboost.py --feature-table app/ml/artifacts/feature_tables/feature_table.parquet
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

# Canonical feature and label maps — must match pipeline.py exactly
from app.ml.features.windowing import FEATURE_COLUMNS
from app.ml.features.pipeline import LABEL_TO_IDX, IDX_TO_LABEL
from app.ml.training.class_weights import compute_class_weights, sample_weights_from_class_weights

N_CLASSES = len(LABEL_TO_IDX)  # 8


def _load_feature_table(parquet_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load pre-built feature table and return (X_train, y_train, X_test, y_test)."""
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Feature table not found: {parquet_path}\n"
            "Run first:  PYTHONPATH=. python app/ml/features/pipeline.py --source csv"
        )
    full = pd.read_parquet(parquet_path)

    # Load train/test splits if they exist alongside the full table
    train_path = parquet_path.parent / "feature_table_train.parquet"
    test_path = parquet_path.parent / "feature_table_test.parquet"

    if train_path.exists() and test_path.exists():
        train_df = pd.read_parquet(train_path)
        test_df = pd.read_parquet(test_path)
    else:
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(
            full, test_size=0.20, stratify=full["label_idx"], random_state=42
        )

    X_train = train_df[FEATURE_COLUMNS].values.astype(np.float32)
    y_train = train_df["label_idx"].values.astype(np.int32)
    X_test = test_df[FEATURE_COLUMNS].values.astype(np.float32)
    y_test = test_df["label_idx"].values.astype(np.int32)

    return X_train, y_train, X_test, y_test


def _build_xgboost_model(n_classes: int):
    """Build an XGBClassifier with settings tuned for this multi-class problem."""
    import xgboost as xgb
    return xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=n_classes,
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",  # fast on CPU
    )


def train_and_evaluate(
    feature_table_path: Path,
    output_dir: Path,
) -> dict:
    """Full training + evaluation loop. Returns metrics summary dict."""
    import xgboost as xgb
    from sklearn.metrics import (
        classification_report,
        confusion_matrix,
        roc_auc_score,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str) -> None:
        logger.info(msg)
        log_lines.append(msg)

    log("=" * 70)
    log("FedRouteAI — XGBoost Centralized Baseline")
    log("=" * 70)

    # ---- Load data ----
    log(f"Loading feature table from: {feature_table_path}")
    X_train, y_train, X_test, y_test = _load_feature_table(feature_table_path)
    log(f"Train: {len(X_train):,} rows | Test: {len(X_test):,} rows | Features: {X_train.shape[1]}")

    # ---- Class weights ----
    log("Computing class weights (inverse-frequency)...")
    cw = compute_class_weights(y_train, n_classes=N_CLASSES)
    sw_train = sample_weights_from_class_weights(y_train, cw)
    for idx, w in enumerate(cw):
        log(f"  {IDX_TO_LABEL[idx]:<20} weight={w:.3f}")

    # ---- Train ----
    log("Training XGBoost (300 rounds, hist tree method)...")
    model = _build_xgboost_model(N_CLASSES)

    eval_results: dict[str, dict] = {}
    model.fit(
        X_train, y_train,
        sample_weight=sw_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=False,
    )

    # ---- Predict ----
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)  # (n_samples, n_classes)

    # ---- Classification report ----
    label_names = [IDX_TO_LABEL[i] for i in range(N_CLASSES)]
    report_str = classification_report(y_test, y_pred, target_names=label_names, digits=4)
    log("\nClassification Report:")
    log(report_str)
    (output_dir / "classification_report.txt").write_text(report_str, encoding="utf-8")

    # ---- Confusion matrix ----
    cm = confusion_matrix(y_test, y_pred, labels=list(range(N_CLASSES)))
    cm_df = pd.DataFrame(cm, index=label_names, columns=label_names)
    cm_df.to_csv(output_dir / "confusion_matrix.csv")
    log("Confusion matrix:")
    log(cm_df.to_string())

    # ---- ROC AUC (one-vs-rest, macro) ----
    try:
        roc_auc_scores: dict[str, float] = {}
        for i, label_name in enumerate(label_names):
            y_binary = (y_test == i).astype(int)
            if y_binary.sum() > 0:
                auc = float(roc_auc_score(y_binary, y_proba[:, i]))
                roc_auc_scores[label_name] = round(auc, 4)

        macro_auc = float(np.mean(list(roc_auc_scores.values())))
        roc_auc_scores["_macro_avg"] = round(macro_auc, 4)
        (output_dir / "roc_auc.json").write_text(
            json.dumps(roc_auc_scores, indent=2), encoding="utf-8"
        )
        log(f"\nROC AUC (macro avg): {macro_auc:.4f}")
    except Exception as e:
        log(f"Warning: ROC AUC computation failed: {e}")
        roc_auc_scores = {}

    # ---- Feature importance ----
    importance_types = ["gain", "weight", "cover"]
    fi_rows = []
    for itype in importance_types:
        scores = model.get_booster().get_score(importance_type=itype)
        for fname, score in scores.items():
            fi_rows.append({"feature": fname, "importance_type": itype, "score": round(score, 4)})

    fi_df = pd.DataFrame(fi_rows)
    # Map f0, f1, ... → actual feature names
    fi_df["feature_name"] = fi_df["feature"].apply(
        lambda f: FEATURE_COLUMNS[int(f[1:])] if f.startswith("f") and f[1:].isdigit() else f
    )
    fi_df.to_csv(output_dir / "feature_importance.csv", index=False)

    log("\nFeature Importance (gain):")
    gain_df = fi_df[fi_df["importance_type"] == "gain"].sort_values("score", ascending=False)
    for _, row in gain_df.iterrows():
        log(f"  {row['feature_name']:<25} {row['score']:.2f}")

    # ---- Summary metrics ----
    from sklearn.metrics import accuracy_score, f1_score
    accuracy = float(accuracy_score(y_test, y_pred))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    metrics = {
        "model": "XGBoost",
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": int(X_train.shape[1]),
        "n_classes": N_CLASSES,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "roc_auc_macro": round(roc_auc_scores.get("_macro_avg", 0.0), 4),
        "class_weights": {IDX_TO_LABEL[i]: round(float(cw[i]), 3) for i in range(N_CLASSES)},
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    log(f"\nSummary:")
    log(f"  Accuracy    : {accuracy:.4f}")
    log(f"  Macro F1    : {macro_f1:.4f}")
    log(f"  Weighted F1 : {weighted_f1:.4f}")

    # ---- Save model ----
    model_path = output_dir / "xgboost_baseline.ubj"
    model.save_model(str(model_path))
    log(f"\nModel saved: {model_path}")

    # ---- Save training log ----
    (output_dir / "training_log.txt").write_text("\n".join(log_lines), encoding="utf-8")
    log(f"Training log: {output_dir / 'training_log.txt'}")
    log("=" * 70)

    return metrics


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(
        description="Train XGBoost baseline and produce research artifacts."
    )
    parser.add_argument(
        "--feature-table",
        default="app/ml/artifacts/feature_tables/feature_table.parquet",
        help="Path to feature_table.parquet (built by pipeline.py).",
    )
    parser.add_argument(
        "--output-dir",
        default="app/ml/artifacts/baseline",
        help="Directory to write all research artifact files.",
    )
    args = parser.parse_args()

    metrics = train_and_evaluate(
        feature_table_path=Path(args.feature_table),
        output_dir=Path(args.output_dir),
    )
    print(f"\n[OK] Baseline complete. Macro F1 = {metrics['macro_f1']:.4f}")
    print(f"  Artifacts in: {args.output_dir}")
