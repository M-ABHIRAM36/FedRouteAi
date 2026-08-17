"""Variable-width Geo V2 MLP matching the trainer checkpoint architecture."""
from __future__ import annotations

import torch
import torch.nn as nn


class GeoV2MLP(nn.Module):
    """V2 MLP copied from the trainer to keep runtime import independent of training."""

    def __init__(self, input_size: int, hidden_size: int = 64, n_classes: int = 8, dropout_rate: float = 0.2) -> None:
        super().__init__()
        if input_size <= 0 or hidden_size < 2 or n_classes != 8:
            raise ValueError("Geo V2 MLP requires positive inputs, hidden_size >= 2, and 8 classes")
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size), nn.BatchNorm1d(hidden_size), nn.ReLU(), nn.Dropout(dropout_rate),
            nn.Linear(hidden_size, hidden_size // 2), nn.BatchNorm1d(hidden_size // 2), nn.ReLU(),
            nn.Linear(hidden_size // 2, n_classes),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return torch.log_softmax(self.net(features), dim=-1)

    def predict_proba(self, features: torch.Tensor) -> torch.Tensor:
        return self(features).exp()
