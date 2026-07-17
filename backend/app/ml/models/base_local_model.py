"""
BaseLocalModel — Abstract interface every FL model variant must satisfy.
------------------------------------------------------------------------
This ABC is the contract between:
  - the Flower client (calls fit/evaluate/get_parameters/set_parameters)
  - the orchestrator (calls predict)
  - AdaptiveFedAvg (receives get_parameters output)

Concrete implementations:
  GaussianLocalModel  — the original mean/std model, kept as cold-start fallback
  MLPLocalModel       — the PyTorch MLP, primary model after Phase 2

Both live in services/federated_learning/local_model.py so flower_server.py
and flower_client.py can import them without reaching into the ml/ package
(which is a training concern, not a live-inference concern).

Future variants (RandomForest, LSTM, GNN, Transformer) only need to implement
this interface — the Flower wiring, AdaptiveFedAvg, and orchestrator stay unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseLocalModel(ABC):
    """Interface contract for all FedRouteAI local model implementations."""

    @classmethod
    @abstractmethod
    def initial(cls) -> "BaseLocalModel":
        """Return a freshly initialized model (random or zero weights).
        Used by flower_server.py to seed the initial global parameters."""

    @abstractmethod
    def get_parameters(self) -> list[np.ndarray]:
        """Flatten model state into a list of numpy arrays.
        Flower uses this for parameter exchange between server and clients.
        The first array's first N_FEATURES elements are stored in
        FLRoundRecord.mean_vector_csv for historical similarity tracking."""

    @abstractmethod
    def set_parameters(self, params: list[np.ndarray]) -> None:
        """Restore model state from the list returned by get_parameters().
        Called by flower_client.py before each local training round to
        apply the global model received from the server."""

    @abstractmethod
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray | None = None,
        *,
        global_params: list[np.ndarray] | None = None,
        class_weights: np.ndarray | None = None,
        epochs: int = 1,
    ) -> float:
        """Train on (X, y) and return a scalar loss.

        Args:
            X: (n_samples, n_features) feature matrix.
            y: (n_samples,) integer class labels. Optional for Gaussian model.
            global_params: If provided, add FedProx regularization term
                           μ/2 * ||w_local - w_global||² to the loss.
                           None during the first round or for GaussianLocalModel.
            class_weights: (n_classes,) per-class loss weights.
                           None = uniform weighting.
            epochs: Number of passes over the training data.

        Returns:
            Scalar training loss (lower is better). Used by Flower for logging
            and by AdaptiveFedAvg's local_loss factor.
        """

    @abstractmethod
    def evaluate(self, X: np.ndarray, y: np.ndarray | None = None) -> float:
        """Compute and return a scalar loss on (X, y).
        Called by flower_client.py's evaluate() method."""

    @abstractmethod
    def predict(self, x: np.ndarray) -> tuple[str, float]:
        """Classify a single feature vector.

        Args:
            x: (n_features,) feature vector (same order as fit()'s X columns).

        Returns:
            (event_type_string, confidence_float) where event_type matches
            constants.EventType values and confidence is in [0.0, 1.0].
            Used by orchestrator.py as the primary classifier.
        """
