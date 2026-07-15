"""Holds the current aggregated global parameters (server-side). A thin
wrapper so API endpoints / evaluation code don't need to know about
Flower internals — they just ask GlobalModelStore for the latest
parameters."""
from dataclasses import dataclass, field

import numpy as np

from app.services.federated_learning.local_model import LocalModel


@dataclass
class GlobalModelStore:
    round_number: int = 0
    model: LocalModel = field(default_factory=LocalModel.initial)

    def update(self, aggregated_params: list[np.ndarray], round_number: int) -> None:
        self.model.set_parameters(aggregated_params)
        self.round_number = round_number

    def as_local_model(self) -> LocalModel:
        """Regions with too little local data can fall back to this
        instead of an undertrained local model — standard FL cold-start
        handling."""
        return self.model


# process-wide singleton for Phase 1 simplicity; swap for a proper store
# (DB row / Redis) once this needs to survive server restarts
GLOBAL_MODEL_STORE = GlobalModelStore()
