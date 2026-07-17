"""
Global Model Store (server-side singleton)
-------------------------------------------
Holds the current aggregated global parameters in memory (no DB roundtrip
on every prediction) and periodically saves to disk so the model survives
server restarts.

This is a process-wide singleton — the same instance is used by:
  - flower_server.py (updates it after each aggregation round)
  - orchestrator.py  (reads from it for ML-primary event classification)
  - endpoints/federated.py (read-only status reporting)

Thread-safety: updates come from the Flower aggregation thread; reads come
from request-handling threads. The update is a single dict assignment
(effectively atomic in CPython due to the GIL), so no explicit locking is
needed for Phase 2. Add a threading.Lock() if moving to a multi-process
server in Phase 4.

Persistence: model weights are saved to artifacts/federated/ every
FL_SAVE_EVERY_N_ROUNDS rounds (configurable). The file format is numpy .npz
— no PyTorch version dependency. Loading restores the full parameter list.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.services.federated_learning.local_model import MLPLocalModel, LocalModel
from app.core.config import settings

logger = logging.getLogger(__name__)

_WEIGHTS_FILENAME = "global_mlp_weights.npz"


@dataclass
class GlobalModelStore:
    round_number: int = 0
    _model: MLPLocalModel = field(default_factory=MLPLocalModel.initial)
    is_trained: bool = False   # False until at least 1 FL round completes

    # ------------------------------------------------------------------
    # Public API used by flower_server.py
    # ------------------------------------------------------------------

    def update(self, aggregated_params: list[np.ndarray], round_number: int) -> None:
        """Apply aggregated FL parameters and optionally persist to disk."""
        self._model.set_parameters(aggregated_params)
        self.round_number = round_number
        self.is_trained = True
        logger.info("GlobalModelStore: updated to round %d", round_number)

        # Periodic disk save
        if round_number % settings.FL_SAVE_EVERY_N_ROUNDS == 0:
            self._save_to_disk()

    def get_parameters(self) -> list[np.ndarray]:
        """Return current global parameters for seeding new Flower rounds."""
        return self._model.get_parameters()

    # ------------------------------------------------------------------
    # Public API used by orchestrator.py
    # ------------------------------------------------------------------

    def predict(self, feature_vec: np.ndarray) -> tuple[str, float] | None:
        """Classify a single 10-feature vector.

        Returns:
            (event_type, confidence) if the global model is trained.
            None if no FL round has completed yet (caller should fall back
            to rule-based pattern_matcher).
        """
        if not self.is_trained:
            return None
        return self._model.predict(feature_vec)

    def as_local_model(self) -> MLPLocalModel:
        """For backward compatibility — used by any code that needs the model object."""
        return self._model

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_to_disk(self) -> None:
        """Save weights as numpy .npz (portable, no torch version dependency)."""
        try:
            out_dir = Path(settings.ML_ARTIFACTS_DIR) / "federated"
            out_dir.mkdir(parents=True, exist_ok=True)
            params = self._model.get_parameters()
            np.savez(str(out_dir / _WEIGHTS_FILENAME), *params)
            logger.info("GlobalModelStore: saved weights → %s (round %d)",
                        out_dir / _WEIGHTS_FILENAME, self.round_number)
        except Exception as exc:
            logger.warning("GlobalModelStore: failed to save weights: %s", exc)

    def load_from_disk(self) -> bool:
        """Attempt to restore weights from disk. Returns True if successful."""
        weights_path = Path(settings.ML_ARTIFACTS_DIR) / "federated" / _WEIGHTS_FILENAME
        if not weights_path.exists():
            return False
        try:
            data = np.load(str(weights_path))
            params = [data[k] for k in sorted(data.files)]
            self._model.set_parameters(params)
            self.is_trained = True
            logger.info("GlobalModelStore: restored weights from disk (%d arrays)", len(params))
            return True
        except Exception as exc:
            logger.warning("GlobalModelStore: failed to load weights: %s", exc)
            return False


# Process-wide singleton — import and use GLOBAL_MODEL_STORE directly
GLOBAL_MODEL_STORE = GlobalModelStore()

# Attempt to restore from disk on startup (e.g. after a server restart)
# This is a best-effort load — if it fails, the store starts untrained
GLOBAL_MODEL_STORE.load_from_disk()
