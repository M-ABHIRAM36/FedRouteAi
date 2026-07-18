"""
Flower Server configuration and evaluation strategy for Federated Learning.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import flwr as fl
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, f1_score, accuracy_score

from app.ml.training.mlp_model import EventClassifierMLP, N_CLASSES
from app.ml.features.pipeline import IDX_TO_LABEL
from app.ml.training.federated_client import set_parameters
from app.ml.training.train_baseline_mlp import load_and_split_data
from app.ml.training.adaptive_fedavg import AdaptiveFedAvg

logger = logging.getLogger(__name__)


def get_evaluate_fn(
    global_feature_table_path: Path,
    output_dir: Path,
    device: torch.device
):
    """Returns an evaluate_fn for centralized global evaluation on the test set."""
    
    logger.info(f"Loading global test set for centralized evaluation from {global_feature_table_path}")
    _, _, (X_test, y_test) = load_and_split_data(global_feature_table_path)
    test_loader = DataLoader(TensorDataset(X_test, y_test), batch_size=128, shuffle=False)
    
    best_macro_f1 = -1.0
    
    def evaluate(server_round: int, parameters: list[np.ndarray], config: dict):
        nonlocal best_macro_f1
        
        model = EventClassifierMLP().to(device)
        set_parameters(model, parameters)
        model.eval()
        
        # In FL evaluation, we don't necessarily have global class weights,
        # Use NLLLoss because EventClassifierMLP.forward() returns log_softmax outputs.
        # (An unweighted NLLLoss is used here purely for tracking the global unweighted loss metric).
        criterion = nn.NLLLoss()
        
        test_loss = 0.0
        test_preds = []
        test_true = []
        test_probs = []
        
        with torch.no_grad():
            for X, y in test_loader:
                X, y = X.to(device), y.to(device)
                
                out = model(X)
                test_loss += criterion(out, y).item() * X.size(0)
                
                probs = model.predict_proba(X)
                preds = torch.argmax(probs, dim=1)
                
                test_probs.append(probs.cpu().numpy())
                test_preds.extend(preds.cpu().numpy())
                test_true.extend(y.cpu().numpy())
                
        test_loss /= len(test_loader.dataset)
        test_preds = np.array(test_preds)
        test_true = np.array(test_true)
        test_probs = np.vstack(test_probs)
        
        accuracy = accuracy_score(test_true, test_preds)
        macro_f1 = f1_score(test_true, test_preds, average="macro", zero_division=0)
        
        # Save checkpoints
        checkpoints_dir = output_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        if server_round % 5 == 0 or server_round == config.get("num_rounds", 30):
            torch.save(model.state_dict(), checkpoints_dir / f"round_{server_round:02d}.pt")
            
        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            torch.save(model.state_dict(), output_dir / "best_global_model.pt")
            
            # Since this is the best model, generate artifacts
            label_names = [IDX_TO_LABEL[i] for i in range(N_CLASSES)]
            report_str = classification_report(test_true, test_preds, target_names=label_names, digits=4, zero_division=0)
            (output_dir / "classification_report.txt").write_text(report_str, encoding="utf-8")
            
            cm = confusion_matrix(test_true, test_preds, labels=list(range(N_CLASSES)))
            cm_df = pd.DataFrame(cm, index=label_names, columns=label_names)
            cm_df.to_csv(output_dir / "confusion_matrix.csv")
            
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
                macro_auc = 0.0
                logger.warning(f"ROC AUC failed: {e}")
                
            (output_dir / "roc_auc.json").write_text(json.dumps(roc_auc_scores, indent=2), encoding="utf-8")
            
            metrics_dict = {
                "round": server_round,
                "accuracy": round(float(accuracy), 4),
                "macro_f1": round(float(macro_f1), 4),
                "roc_auc_macro": round(macro_auc, 4),
            }
            (output_dir / "metrics.json").write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")
            
        logger.info(f"Round {server_round} Evaluation: Loss={test_loss:.4f} | Acc={accuracy:.4f} | Macro F1={macro_f1:.4f}")
        return float(test_loss), {"accuracy": float(accuracy), "macro_f1": float(macro_f1)}
        
    return evaluate

def get_strategy(
    global_feature_table_path: Path,
    output_dir: Path,
    device: torch.device,
    num_rounds: int
) -> fl.server.strategy.Strategy:
    """Returns configured FedAvg strategy."""
    
    # We must provide initial_parameters so it can evaluate at round 0
    model = EventClassifierMLP()
    from app.ml.training.federated_client import get_parameters
    initial_parameters = fl.common.ndarrays_to_parameters(get_parameters(model))
    
    return fl.server.strategy.FedAvg(
        fraction_fit=1.0,  # Sample all 8 clients
        fraction_evaluate=0.0, # We use centralized evaluation, so no distributed eval
        min_fit_clients=8,
        min_available_clients=8,
        initial_parameters=initial_parameters,
        evaluate_fn=get_evaluate_fn(global_feature_table_path, output_dir, device),
        on_fit_config_fn=lambda round: {"num_rounds": num_rounds} # pass num_rounds to evaluate via config
    )


def compute_global_class_frequencies(global_feature_table_path: Path) -> dict[int, float]:
    """Computes global class frequencies to identify rare classes."""
    if not global_feature_table_path.exists():
        logger.warning(f"Feature table not found at {global_feature_table_path}. Cannot compute class frequencies.")
        return {}
        
    df = pd.read_parquet(global_feature_table_path)
    if "label_idx" not in df.columns:
        return {}
        
    counts = df["label_idx"].value_counts(normalize=True)
    return counts.to_dict()


def get_adaptive_strategy(
    global_feature_table_path: Path,
    output_dir: Path,
    device: torch.device,
    num_rounds: int,
    alpha: float = 0.3,
    beta: float = 0.3,
    q_floor: float = 0.10,
    g_threshold: float = 0.15,
    g_min: float = 0.50,
    rare_threshold: float = 0.05
) -> fl.server.strategy.Strategy:
    """Returns configured AdaptiveFedAvg strategy."""
    
    # We must provide initial_parameters so it can evaluate at round 0
    model = EventClassifierMLP()
    from app.ml.training.federated_client import get_parameters
    initial_parameters = fl.common.ndarrays_to_parameters(get_parameters(model))
    
    global_class_frequencies = compute_global_class_frequencies(global_feature_table_path)
    
    rare_classes = [
        cls_idx for cls_idx, freq in global_class_frequencies.items() 
        if freq < rare_threshold
    ]
    rare_classes_str = ",".join(str(c) for c in rare_classes)
    
    return AdaptiveFedAvg(
        global_class_frequencies=global_class_frequencies,
        alpha=alpha,
        beta=beta,
        q_floor=q_floor,
        g_threshold=g_threshold,
        g_min=g_min,
        rare_threshold=rare_threshold,
        weight_log_path=output_dir / "adaptive_weights.csv",
        fraction_fit=1.0,  # Sample all 8 clients
        fraction_evaluate=0.0, # We use centralized evaluation, so no distributed eval
        min_fit_clients=8,
        min_available_clients=8,
        initial_parameters=initial_parameters,
        evaluate_fn=get_evaluate_fn(global_feature_table_path, output_dir, device),
        on_fit_config_fn=lambda round: {
            "num_rounds": num_rounds,
            "rare_classes": rare_classes_str
        }
    )
