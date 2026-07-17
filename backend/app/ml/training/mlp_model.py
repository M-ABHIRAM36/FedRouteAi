"""
PyTorch MLP for multi-class event classification.
----------------------------------------------------
Architecture:
    Input(10) → Linear(10,64) → BatchNorm1d → ReLU → Dropout(0.2)
              → Linear(64,32) → BatchNorm1d → ReLU
              → Linear(32,8)  → LogSoftmax

Design choices:
  - BatchNorm instead of LayerNorm: better for small tabular batches
  - LogSoftmax output: works with NLLLoss (and CrossEntropyLoss uses softmax internally)
  - Dropout only on first hidden layer: dataset is small enough that
    double dropout can underfit on per-region subsets
  - 8 output classes: normal + 7 event types (see LABEL_TO_IDX / IDX_TO_LABEL)
  - 10 input features: matches windowing.py::FEATURE_COLUMNS

This module is imported by:
  - services/federated_learning/local_model.py  (MLPLocalModel wraps this)
  - training/train_mlp_standalone.py            (offline evaluation)
"""
from __future__ import annotations

import torch
import torch.nn as nn

# Canonical label ↔ index mapping (must match pipeline.py's LABEL_TO_IDX)
LABEL_TO_IDX: dict[str, int] = {
    "normal": 0,
    "congestion": 1,
    "construction": 2,
    "flood": 3,
    "road_block": 4,
    "road_damage": 5,
    "accident": 6,
    "diversion": 7,
}
IDX_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_IDX.items()}

N_INPUT = 10   # must match windowing.py::N_FEATURES
N_HIDDEN = 64  # must match settings.MLP_HIDDEN_SIZE
N_CLASSES = 8  # must match settings.MLP_NUM_CLASSES


class EventClassifierMLP(nn.Module):
    """Lightweight MLP for GPS-pattern event classification."""

    def __init__(
        self,
        input_size: int = N_INPUT,
        hidden_size: int = N_HIDDEN,
        n_classes: int = N_CLASSES,
        dropout_rate: float = 0.2,
    ) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, n_classes),
        )
        # Initialize weights with Xavier uniform for stable training
        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, input_size) → log-probabilities: (batch, n_classes)"""
        logits = self.net(x)
        return torch.log_softmax(logits, dim=-1)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return probabilities (not log-probs) for inference."""
        with torch.no_grad():
            log_probs = self.forward(x)
        return torch.exp(log_probs)
