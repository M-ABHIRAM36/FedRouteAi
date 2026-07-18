"""
Flower NumPyClient for regional FL training.
"""
from __future__ import annotations

import time
import logging
from pathlib import Path
from collections import OrderedDict

import flwr as fl
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import f1_score

from app.ml.training.mlp_model import EventClassifierMLP, N_CLASSES
from app.ml.training.class_weights import compute_class_weights
from app.ml.training.train_baseline_mlp import load_and_split_data

logger = logging.getLogger(__name__)


def set_parameters(model: nn.Module, parameters: list[np.ndarray]) -> None:
    params_dict = zip(model.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)


def get_parameters(model: nn.Module) -> list[np.ndarray]:
    return [val.cpu().numpy() for _, val in model.state_dict().items()]


class RegionalFedRouteClient(fl.client.NumPyClient):
    def __init__(self, region_id: str, data_dir: Path, device: torch.device):
        self.region_id = region_id
        self.device = device
        self.model = EventClassifierMLP().to(self.device)
        
        # Load local regional data
        region_parquet = data_dir / f"feature_table_{self.region_id}.parquet"
        try:
            # We reuse the centralized splitter to ensure identical prep (70/15/15)
            # This correctly handles rare classes with <2 samples by dropping them locally
            (X_train, y_train, y_train_np), (X_val, y_val), (X_test, y_test) = load_and_split_data(region_parquet)
            self.train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=128, shuffle=True)
            self.val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=128, shuffle=False)
            self.n_samples = len(X_train)
            
            # Compute class weights for this specific region
            cw = compute_class_weights(y_train_np, n_classes=N_CLASSES)
            self.class_weights = torch.tensor(cw, dtype=torch.float32).to(self.device)
            self.valid_data = True
            
        except Exception as e:
            logger.warning(f"Region {self.region_id} failed to load data: {e}")
            self.valid_data = False
            self.n_samples = 0

    def get_parameters(self, config):
        return get_parameters(self.model)

    def fit(self, parameters, config):
        set_parameters(self.model, parameters)
        
        if not self.valid_data or self.n_samples == 0:
            return get_parameters(self.model), 0, {"region_id": self.region_id, "train_loss": 999.0}

        start_time = time.time()
        
        criterion = nn.NLLLoss(weight=self.class_weights)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-3)
        epochs = 3
        
        self.model.train()
        total_loss = 0.0
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for X, y in self.train_loader:
                X, y = X.to(self.device), y.to(self.device)
                optimizer.zero_grad()
                out = self.model(X)
                loss = criterion(out, y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * X.size(0)
            total_loss += epoch_loss
            
        avg_train_loss = total_loss / (epochs * self.n_samples)
        
        # Local Validation
        self.model.eval()
        val_loss = 0.0
        val_preds = []
        val_true = []
        with torch.no_grad():
            for X, y in self.val_loader:
                X, y = X.to(self.device), y.to(self.device)
                out = self.model(X)
                val_loss += criterion(out, y).item() * X.size(0)
                preds = torch.argmax(out, dim=1)
                val_preds.extend(preds.cpu().numpy())
                val_true.extend(y.cpu().numpy())
                
        val_loss /= len(self.val_loader.dataset) if len(self.val_loader.dataset) > 0 else 1
        val_macro_f1 = f1_score(val_true, val_preds, average="macro", zero_division=0)
        
        train_time = time.time() - start_time
        
        # Return local metrics for future AdaptiveFedAvg
        metrics = {
            "region_id": self.region_id,
            "train_loss": float(avg_train_loss),
            "val_loss": float(val_loss),
            "val_macro_f1": float(val_macro_f1),
            "train_time": float(train_time),
            "dataset_size": self.n_samples
        }
        
        return get_parameters(self.model), self.n_samples, metrics

    def evaluate(self, parameters, config):
        # We don't perform federated evaluation on clients (we do centralized test set eval on the server).
        return 0.0, self.n_samples, {"region_id": self.region_id}
