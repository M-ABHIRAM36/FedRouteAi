"""
Replay Buffer
--------------
Prevents catastrophic forgetting of rare/severe events during sequential
local training rounds. Each Flower client maintains one per-region buffer
that persists across FL rounds.

Design:
  - Stores ReplayExample dataclass instances (rich metadata, not just vectors)
  - Priority retention for rare/severe event classes (configurable)
  - Reservoir sampling for normal/common class overflow
  - Enables future: top-K replay, priority replay, time-decay replay —
    all metadata needed is already stored in ReplayExample

Usage:
    buffer = ReplayBuffer(max_size=500)
    buffer.add_batch(X_features, y_labels, region_id="REGION_01",
                     timestamps=ts_array, severities=sev_array)
    X_replay, y_replay = buffer.sample(n=64)
    # Concatenate with current batch before training
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# Event classes considered rare/severe — always retained if buffer is full
# (matches the bottom of the label distribution we observed in EDA)
RARE_LABELS: frozenset[int] = frozenset([3, 4, 6, 7])  # flood, road_block, accident, diversion


@dataclass
class ReplayExample:
    """One replay-buffer entry. Rich metadata enables future replay strategies."""
    features: np.ndarray        # (n_features,) float32 feature vector
    label: int                  # integer class index
    region_id: str              # which region produced this example
    timestamp: datetime         # when this window occurred
    severity: float = 0.0       # event severity [0,1]; 0 for normal windows
    confidence: float = 1.0     # model's own confidence at time of storage
                                # (for uncertainty-based replay in future)


class ReplayBuffer:
    """Per-region replay buffer with priority retention for rare events.

    Thread-safety: NOT thread-safe — this is fine because each Flower client
    process runs single-threaded (one client per region).
    """

    def __init__(
        self,
        max_size: int = 500,
        rare_labels: frozenset[int] = RARE_LABELS,
        random_seed: int | None = None,
    ) -> None:
        self.max_size = max_size
        self.rare_labels = rare_labels
        self._buffer: list[ReplayExample] = []
        self._rng = random.Random(random_seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_batch(
        self,
        X: np.ndarray,
        y: np.ndarray,
        region_id: str,
        timestamps: np.ndarray | None = None,
        severities: np.ndarray | None = None,
        confidences: np.ndarray | None = None,
    ) -> None:
        """Add a batch of training examples to the buffer.

        Args:
            X:           (n, n_features) feature matrix
            y:           (n,) integer class labels
            region_id:   region that produced this data
            timestamps:  (n,) datetime array; defaults to utcnow()
            severities:  (n,) float array [0,1]; defaults to 0.0
            confidences: (n,) float array [0,1]; defaults to 1.0
        """
        n = len(X)
        if n == 0:
            return

        now = datetime.utcnow()
        for i in range(n):
            example = ReplayExample(
                features=X[i].astype(np.float32),
                label=int(y[i]),
                region_id=region_id,
                timestamp=timestamps[i] if timestamps is not None else now,
                severity=float(severities[i]) if severities is not None else 0.0,
                confidence=float(confidences[i]) if confidences is not None else 1.0,
            )
            self._insert(example)

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Sample up to n examples for replay training.

        Returns:
            (X, y) arrays; X shape (min(n, len(buffer)), n_features)
        """
        if not self._buffer:
            return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.int32)

        k = min(n, len(self._buffer))
        chosen = self._rng.sample(self._buffer, k)
        X = np.stack([e.features for e in chosen], axis=0)
        y = np.array([e.label for e in chosen], dtype=np.int32)
        return X, y

    def __len__(self) -> int:
        return len(self._buffer)

    def rare_count(self) -> int:
        """Number of rare-class examples currently in the buffer."""
        return sum(1 for e in self._buffer if e.label in self.rare_labels)

    def label_distribution(self) -> dict[int, int]:
        """Current label distribution in the buffer."""
        dist: dict[int, int] = {}
        for e in self._buffer:
            dist[e.label] = dist.get(e.label, 0) + 1
        return dist

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _insert(self, example: ReplayExample) -> None:
        """Insert one example, evicting a common-class example if full."""
        if len(self._buffer) < self.max_size:
            self._buffer.append(example)
            return

        # Buffer is full — choose eviction strategy:
        # Rare/severe events: always keep (evict a common-class example instead)
        # Common events: reservoir sampling (random eviction)
        if example.label in self.rare_labels:
            # Evict a random non-rare example to make room
            common_indices = [
                i for i, e in enumerate(self._buffer) if e.label not in self.rare_labels
            ]
            if common_indices:
                evict_idx = self._rng.choice(common_indices)
                self._buffer[evict_idx] = example
            # If all entries are already rare, skip (buffer fully dedicated to rare classes)
        else:
            # Standard reservoir: replace a random entry with probability max_size / (n+1)
            # Simplified: just replace a random common-class entry (FIFO-ish)
            common_indices = [
                i for i, e in enumerate(self._buffer) if e.label not in self.rare_labels
            ]
            if common_indices:
                evict_idx = self._rng.choice(common_indices)
                self._buffer[evict_idx] = example
            # If no common entries, skip (don't evict rare for common)
