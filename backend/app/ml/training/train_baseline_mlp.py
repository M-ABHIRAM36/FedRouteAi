"""
Centralized PyTorch MLP Baseline Training
---------------------------------------
Trains the PyTorch MLP classifier on the centralized (global) feature table and
produces a complete set of research artifacts.

Outputs (all to app/ml/artifacts/baseline/mlp/):
  mlp_baseline.pt             - trained model weights
  classification_report.txt   - per-class precision / recall / F1 / support
  confusion_matrix.csv        - 8x8 matrix (true vs predicted)
  roc_auc.json                - per-class one-vs-rest AUC scores
  metrics.json                - summary (accuracy, macro F1, weighted F1)
  training_history.csv        - epoch-by-epoch loss and F1
  config.json                 - hyperparameters

Usage:
    cd backend
    PYTHONPATH=. python app/ml/training/train_baseline_mlp.py
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, f1_score, accuracy_score

# --- Import from Project Architecture ---
from app.ml.features.windowing import FEATURE_COLUMNS
from app.ml.features.pipeline import LABEL_TO_IDX, IDX_TO_LABEL
from app.ml.training.class_weights import compute_class_weights
from app.ml.training.mlp_model import EventClassifierMLP, N_CLASSES

logger = logging.getLogger(__name__)

# --- Reproducibility ---
def seed_everything(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

# --- Data Loading ---
def load_and_split_data(parquet_path: Path):
    if not parquet_path.exists():
        raise FileNotFoundError(f"Feature table not found: {parquet_path}")
    
    full_df = pd.read_parquet(parquet_path)
    
    # Drop rows without required labels if any missing values
    full_df = full_df.dropna(subset=["label_idx"])
    
    # Ensure classes with less than 2 instances don't break stratified split
    counts = full_df["label_idx"].value_counts()
    valid = counts[counts >= 2].index
    df = full_df[full_df["label_idx"].isin(valid)].copy()
    if len(df) < len(full_df):
        logger.warning(f"Dropped {len(full_df)-len(df)} rows due to rare classes (< 2 samples)")
    
    # Stratified split: 70% train, 15% val, 15% test
    train_df, temp_df = train_test_split(
        df, test_size=0.30, stratify=df["label_idx"], random_state=42
    )
    
    # Drop any classes that appear < 2 times in temp_df before second split
    counts_temp = temp_df["label_idx"].value_counts()
    valid_temp = counts_temp[counts_temp >= 2].index
    temp_df = temp_df[temp_df["label_idx"].isin(valid_temp)].copy()

    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, stratify=temp_df["label_idx"], random_state=42
    )
    
    def extract_tensors(d):
        X = torch.tensor(d[FEATURE_COLUMNS].values, dtype=torch.float32)
        y = torch.tensor(d["label_idx"].values, dtype=torch.long)
        return X, y

    X_train, y_train = extract_tensors(train_df)
    X_val, y_val = extract_tensors(val_df)
    X_test, y_test = extract_tensors(test_df)
    
    return (X_train, y_train, train_df["label_idx"].values), (X_val, y_val), (X_test, y_test)

# --- Main Training Routine ---
def train_and_evaluate(feature_table_path: Path, output_dir: Path):
    seed_everything(42)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Hyperparameters
    batch_size = 128
    epochs = 100
    patience = 10
    min_delta = 0.001
    lr = 1e-3
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    config = {
        "learning_rate": lr,
        "optimizer": "AdamW",
        "batch_size": batch_size,
        "epochs": epochs,
        "patience": patience,
        "architecture_name": "EventClassifierMLP",
        "random_seed": 42
    }
    (output_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    
    logger.info("=" * 70)
    logger.info(f"FedRouteAI — MLP Centralized Baseline (Device: {device})")
    logger.info("=" * 70)

    # 1. Load Data
    logger.info(f"Loading data from: {feature_table_path}")
    (X_train, y_train, y_train_np), (X_val, y_val), (X_test, y_test) = load_and_split_data(feature_table_path)
    logger.info(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    
    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(X_test, y_test), batch_size=batch_size, shuffle=False)

    # 2. Setup Model & Loss
    model = EventClassifierMLP().to(device)
    
    # Compute inverse-frequency class weights based ONLY on training set
    cw = compute_class_weights(y_train_np, n_classes=N_CLASSES)
    class_weights_tensor = torch.tensor(cw, dtype=torch.float32).to(device)
    
    criterion = nn.NLLLoss(weight=class_weights_tensor)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    
    # 3. Training Loop with Early Stopping
    best_val_loss = float('inf')
    epochs_no_improve = 0
    history = []
    
    best_model_path = output_dir / "mlp_baseline.pt"
    
    logger.info("Starting training...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            log_probs = model(batch_X)
            loss = criterion(log_probs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_X.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_preds = []
        val_true = []
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                log_probs = model(batch_X)
                loss = criterion(log_probs, batch_y)
                val_loss += loss.item() * batch_X.size(0)
                
                preds = torch.argmax(log_probs, dim=1)
                val_preds.extend(preds.cpu().numpy())
                val_true.extend(batch_y.cpu().numpy())
                
        val_loss /= len(val_loader.dataset)
        val_macro_f1 = f1_score(val_true, val_preds, average='macro', zero_division=0)
        
        history.append({
            "Epoch": epoch,
            "Train Loss": round(float(train_loss), 4),
            "Validation Loss": round(float(val_loss), 4),
            "Validation Macro F1": round(float(val_macro_f1), 4)
        })
        
        logger.info(f"Epoch {epoch:03d}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val F1: {val_macro_f1:.4f}")
        
        # Early Stopping Logic (monitor validation loss)
        if val_loss < best_val_loss - min_delta:
            best_val_loss = val_loss
            epochs_no_improve = 0
            # Save best model
            torch.save(model.state_dict(), str(best_model_path))
        else:
            epochs_no_improve += 1
            
        if epochs_no_improve >= patience:
            logger.info(f"Early stopping triggered after {epoch} epochs.")
            break

    pd.DataFrame(history).to_csv(output_dir / "training_history.csv", index=False)
    
    # 4. Evaluation on TEST set
    logger.info("=" * 70)
    logger.info("Evaluating on held-out test set...")
    
    # Load best model
    if best_model_path.exists():
        model.load_state_dict(torch.load(str(best_model_path), weights_only=True))
    model.eval()
    
    test_preds = []
    test_true = []
    test_probs = []
    with torch.no_grad():
        for batch_X, batch_y in test_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            # Use predict_proba for ROC AUC (probabilities, not log-probs)
            probs = model.predict_proba(batch_X)
            preds = torch.argmax(probs, dim=1)
            
            test_probs.append(probs.cpu().numpy())
            test_preds.extend(preds.cpu().numpy())
            test_true.extend(batch_y.cpu().numpy())
            
    test_preds = np.array(test_preds)
    test_true = np.array(test_true)
    test_probs = np.vstack(test_probs)
    
    label_names = [IDX_TO_LABEL[i] for i in range(N_CLASSES)]
    
    # Classification Report
    report_str = classification_report(test_true, test_preds, target_names=label_names, digits=4, zero_division=0)
    (output_dir / "classification_report.txt").write_text(report_str, encoding="utf-8")
    logger.info("\nClassification Report:\n" + report_str)
    
    # Confusion Matrix
    cm = confusion_matrix(test_true, test_preds, labels=list(range(N_CLASSES)))
    cm_df = pd.DataFrame(cm, index=label_names, columns=label_names)
    cm_df.to_csv(output_dir / "confusion_matrix.csv")
    
    # ROC AUC
    roc_auc_scores = {}
    try:
        for i, label_name in enumerate(label_names):
            y_binary = (test_true == i).astype(int)
            if y_binary.sum() > 0:
                auc = float(roc_auc_score(y_binary, test_probs[:, i]))
                roc_auc_scores[label_name] = round(auc, 4)
                
        macro_auc = float(np.mean(list(roc_auc_scores.values())))
        roc_auc_scores["_macro_avg"] = round(macro_auc, 4)
    except Exception as e:
        logger.warning(f"ROC AUC computation failed: {e}")
        macro_auc = 0.0

    (output_dir / "roc_auc.json").write_text(json.dumps(roc_auc_scores, indent=2), encoding="utf-8")
    
    # Summary Metrics
    accuracy = float(accuracy_score(test_true, test_preds))
    macro_f1 = float(f1_score(test_true, test_preds, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(test_true, test_preds, average="weighted", zero_division=0))
    
    metrics = {
        "model": "EventClassifierMLP",
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "n_features": len(FEATURE_COLUMNS),
        "n_classes": N_CLASSES,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "roc_auc_macro": round(macro_auc, 4),
        "class_weights": {IDX_TO_LABEL[i]: round(float(cw[i]), 3) for i in range(N_CLASSES)},
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    
    logger.info(f"Test Accuracy: {accuracy:.4f}")
    logger.info(f"Test Macro F1: {macro_f1:.4f}")
    logger.info(f"Test Weighted F1: {weighted_f1:.4f}")
    logger.info(f"Artifacts saved to {output_dir}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="Train PyTorch MLP baseline.")
    parser.add_argument(
        "--feature-table",
        default="data/calibration/high/features/feature_table.parquet",
        help="Path to feature_table.parquet",
    )
    parser.add_argument(
        "--output-dir",
        default="app/ml/artifacts/baseline/mlp",
        help="Directory to write all research artifact files.",
    )
    args = parser.parse_args()

    train_and_evaluate(Path(args.feature_table), Path(args.output_dir))
