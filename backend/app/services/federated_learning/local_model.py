"""
Local Models (per region)
---------------------------
Two model implementations, both satisfying the BaseLocalModel interface:

  GaussianLocalModel  — the original Phase 1 model. Kept as:
                         1. Cold-start fallback when a region has < 10 samples
                         2. Reference baseline for ablation studies
                         3. Proof that the FL plumbing works without a GPU

  MLPLocalModel       — PyTorch MLP with FedProx regularization, class-weighted
                         loss, and replay buffer support. Primary model once any
                         FL round has completed.

The existing `LocalModel` name is aliased to `MLPLocalModel` so all code that
imports `from app.services.federated_learning.local_model import LocalModel`
continues to work without changes.

flower_server.py:   LocalModel.initial() → creates an MLPLocalModel with Xavier init
flower_client.py:   model.fit(X, y, global_params, class_weights, replay_buffer) → trains MLP
adaptive_aggregation.py: model.get_parameters() → list of weight tensors as numpy arrays
                          mean_vector_csv stores arrays[0].flatten()[:10] (first 10 of W1)
orchestrator.py:    GlobalModelStore → model.predict(feature_vec) → (event_type, confidence)
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from app.ml.models.base_local_model import BaseLocalModel
from app.ml.training.mlp_model import EventClassifierMLP, IDX_TO_LABEL, LABEL_TO_IDX, N_INPUT, N_CLASSES


# ──────────────────────────────────────────────────────────────────────────────
# GaussianLocalModel  (Phase 1 model — preserved, demoted to fallback)
# ──────────────────────────────────────────────────────────────────────────────

N_FEATURES = 4  # speed_ratio, density_ratio, uturn_ratio, variance_ratio


class GaussianLocalModel(BaseLocalModel):
    """Learned Gaussian baseline (mean/std) over 4 behavioral-signature features.

    Kept from Phase 1 — useful for cold-start regions and as a baseline
    comparison. Does NOT use labels (unsupervised: learns what 'normal' looks
    like, then deviation_score() measures anomaly distance).
    """

    def __init__(self, mean: np.ndarray, std: np.ndarray, n_samples: int = 0) -> None:
        self.mean = mean
        self.std = std
        self.n_samples = n_samples

    @classmethod
    def initial(cls) -> "GaussianLocalModel":
        return cls(
            mean=np.ones(N_FEATURES, dtype=np.float32),
            std=np.ones(N_FEATURES, dtype=np.float32) * 0.2,
            n_samples=0,
        )

    def get_parameters(self) -> list[np.ndarray]:
        return [self.mean, self.std]

    def set_parameters(self, params: list[np.ndarray]) -> None:
        self.mean, self.std = params[0], params[1]

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray | None = None,
        *,
        global_params: list[np.ndarray] | None = None,
        class_weights: np.ndarray | None = None,
        epochs: int = 1,
    ) -> float:
        """Closed-form Gaussian fit (ignores y, global_params, class_weights)."""
        # Use only the first 4 features (speed/density/uturn/variance ratios)
        X4 = X[:, :N_FEATURES] if X.shape[1] >= N_FEATURES else X
        self.mean = X4.mean(axis=0).astype(np.float32)
        self.std = (X4.std(axis=0) + 1e-3).astype(np.float32)
        self.n_samples = len(X4)
        z = (X4 - self.mean) / self.std
        return float(np.mean(0.5 * z ** 2))

    def evaluate(self, X: np.ndarray, y: np.ndarray | None = None) -> float:
        X4 = X[:, :N_FEATURES] if X.shape[1] >= N_FEATURES else X
        z = (X4 - self.mean) / self.std
        return float(np.mean(0.5 * z ** 2))

    def predict(self, x: np.ndarray) -> tuple[str, float]:
        """Deviation-based 'prediction': if within 1 std → normal, else unknown."""
        x4 = x[:N_FEATURES] if len(x) >= N_FEATURES else x
        z = (x4 - self.mean) / self.std
        deviation = float(np.sqrt(np.mean(z ** 2)))
        if deviation < 1.0:
            return "normal", round(1.0 - deviation / 2.0, 3)
        # Can't classify event type — return low-confidence normal
        return "normal", 0.3

    def deviation_score(self, x: np.ndarray) -> float:
        """Legacy method kept for any code that calls it directly."""
        x4 = x[:N_FEATURES] if len(x) >= N_FEATURES else x
        z = (x4 - self.mean) / self.std
        return float(np.sqrt(np.mean(z ** 2)))


# ──────────────────────────────────────────────────────────────────────────────
# MLPLocalModel  (Phase 2 — primary model)
# ──────────────────────────────────────────────────────────────────────────────

# How many values from the first weight matrix to store in mean_vector_csv
# (FLRoundRecord.mean_vector_csv is String(200); 10 floats × ~8 chars = ~80)
_COMPAT_VECTOR_LEN = 10


class MLPLocalModel(BaseLocalModel):
    """PyTorch MLP event classifier with FedProx regularization.

    FedProx: adds μ/2 * ||w_local - w_global||² to the loss during fit().
    This constrains local updates to not drift too far from the global model,
    which is especially important for the heterogeneous regional data
    distributions in FedRouteAI (each region has different event mix).

    Class weights: passed into fit() from flower_client.py. Computed once per
    round from the region's current training set.

    Replay buffer: flower_client.py passes in its per-region buffer; this class
    samples from it and concatenates with the current batch.
    """

    def __init__(
        self,
        input_size: int = N_INPUT,
        hidden_size: int = 64,
        n_classes: int = N_CLASSES,
        mu: float = 0.01,  # FedProx regularization strength
    ) -> None:
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_classes = n_classes
        self.mu = mu
        self.net = EventClassifierMLP(input_size, hidden_size, n_classes)
        self._device = torch.device("cpu")

    @classmethod
    def initial(cls) -> "MLPLocalModel":
        """Return a freshly Xavier-initialized model (weights ≠ 0).
        Used by flower_server.py to seed the initial global parameters."""
        return cls()  # __init__ calls _init_weights via EventClassifierMLP

    def get_parameters(self) -> list[np.ndarray]:
        """Return all weight tensors as numpy arrays.
        Returns [W1, b1, BN1_weight, BN1_bias, BN1_mean, BN1_var,
                 W2, b2, BN2_weight, BN2_bias, BN2_mean, BN2_var,
                 W3, b3]
        AdaptiveFedAvg uses arrays[0] (W1) for historical_similarity.
        """
        return [p.data.cpu().numpy() for p in self.net.parameters()]

    def set_parameters(self, params: list[np.ndarray]) -> None:
        """Load parameter list back into the model.
        Called by flower_client.py before each local training round."""
        state = self.net.state_dict()
        for (name, _), array in zip(state.items(), params):
            state[name] = torch.tensor(array)
        self.net.load_state_dict(state)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray | None = None,
        *,
        global_params: list[np.ndarray] | None = None,
        class_weights: np.ndarray | None = None,
        epochs: int = 5,
        replay_buffer=None,   # ReplayBuffer | None — avoid circular import
        learning_rate: float = 1e-3,
    ) -> float:
        """Train the MLP with optional FedProx, class weights, and replay.

        Args:
            X: (n, 10) feature matrix (windowed, ratio features only)
            y: (n,) integer class labels (required for MLP)
            global_params: weights snapshot before local training — used for FedProx penalty
            class_weights: (n_classes,) per-class loss multipliers
            epochs: local gradient descent passes
            replay_buffer: if provided, samples from it and adds to training batch
            learning_rate: Adam LR

        Returns:
            Final training loss (scalar).
        """
        if y is None:
            raise ValueError("MLPLocalModel.fit() requires labels (y). "
                             "Use GaussianLocalModel for unsupervised training.")

        # ---- Augment with replay examples ----
        if replay_buffer is not None and len(replay_buffer) > 0:
            X_replay, y_replay = replay_buffer.sample(n=min(64, len(replay_buffer)))
            if len(X_replay) > 0:
                X = np.concatenate([X, X_replay], axis=0)
                y = np.concatenate([y, y_replay], axis=0)

        X_t = torch.tensor(X, dtype=torch.float32).to(self._device)
        y_t = torch.tensor(y, dtype=torch.long).to(self._device)

        # ---- Loss function with optional class weights ----
        if class_weights is not None:
            w = torch.tensor(class_weights, dtype=torch.float32).to(self._device)
        else:
            w = None
        # NLLLoss + LogSoftmax output (equivalent to CrossEntropyLoss but explicit)
        criterion = nn.NLLLoss(weight=w)

        # ---- Snapshot global parameters for FedProx ----
        global_tensors: list[torch.Tensor] | None = None
        if global_params is not None and self.mu > 0:
            global_tensors = [
                torch.tensor(p, dtype=torch.float32).to(self._device)
                for p in global_params
            ]

        optimizer = torch.optim.Adam(self.net.parameters(), lr=learning_rate)
        self.net.train()
        final_loss = 0.0

        for epoch in range(epochs):
            optimizer.zero_grad()
            log_probs = self.net(X_t)
            ce_loss = criterion(log_probs, y_t)

            # ---- FedProx regularization term ----
            prox_loss = torch.tensor(0.0)
            if global_tensors is not None:
                local_params = list(self.net.parameters())
                for lp, gp in zip(local_params, global_tensors):
                    prox_loss = prox_loss + torch.sum((lp - gp) ** 2)
                prox_loss = (self.mu / 2.0) * prox_loss

            total_loss = ce_loss + prox_loss
            total_loss.backward()
            optimizer.step()
            final_loss = float(total_loss.item())

        self.net.eval()
        return final_loss

    def evaluate(self, X: np.ndarray, y: np.ndarray | None = None) -> float:
        """Compute NLL loss on (X, y)."""
        if y is None:
            return 0.0
        self.net.eval()
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32)
            y_t = torch.tensor(y, dtype=torch.long)
            log_probs = self.net(X_t)
            loss = nn.NLLLoss()(log_probs, y_t)
        return float(loss.item())

    def predict(self, x: np.ndarray) -> tuple[str, float]:
        """Classify a single feature vector.

        Returns:
            (event_type_string, confidence) where confidence ∈ [0, 1].
            Used by orchestrator.py as the primary event classifier.
        """
        self.net.eval()
        with torch.no_grad():
            x_t = torch.tensor(x, dtype=torch.float32).unsqueeze(0)  # (1, 10)
            proba = self.net.predict_proba(x_t).squeeze(0)            # (8,)
        class_idx = int(torch.argmax(proba).item())
        confidence = float(proba[class_idx].item())
        return IDX_TO_LABEL[class_idx], round(confidence, 3)

    def get_compat_vector(self) -> np.ndarray:
        """Return a compact vector for FLRoundRecord.mean_vector_csv.
        Stores first _COMPAT_VECTOR_LEN values of W1 (first weight matrix).
        These track how input-feature sensitivity evolves across rounds
        — used by AdaptiveFedAvg's historical_similarity computation.
        """
        params = self.get_parameters()
        w1 = params[0].flatten()
        return w1[:_COMPAT_VECTOR_LEN].astype(np.float32)


# ── Alias so existing `from local_model import LocalModel` imports keep working ──
# flower_server.py and flower_client.py use this name.
LocalModel = MLPLocalModel
