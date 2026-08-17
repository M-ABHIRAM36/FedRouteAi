"""Validated, thread-safe loader for Geo V2 federated model artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np
import torch

from app.core.config import settings
from app.ml.geo_v2.features import FEATURE_VARIANTS, reject_forbidden_columns
from app.ml.geo_v2.model import GeoV2MLP


DEFAULT_LABELS = ("normal", "congestion", "construction", "flood", "road_block", "road_damage", "accident", "diversion")


@dataclass(frozen=True)
class GeoV2Prediction:
    status: str
    model_version: str | None
    probabilities: list[dict[str, float]] | None
    error: str | None = None


class GeoV2ModelStore:
    """Load only complete artifacts; an unavailable model can never emit a label."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or settings.GEO_V2_MODEL_PATH
        if configured:
            candidate = Path(configured)
            self.path = candidate if candidate.is_absolute() else Path(__file__).resolve().parents[3] / candidate
        else:
            self.path = Path(__file__).resolve().parents[1] / "artifacts" / "geo_v2" / "federated" / "current" / "best_global_model.pt"
        self._lock = RLock()
        self._model: GeoV2MLP | None = None
        self._feature_order: tuple[str, ...] = ()
        self._mean: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._labels: tuple[str, ...] = ()
        self._version: str | None = None
        self._stamp: tuple[int, int] | None = None
        self._error: str | None = None

    @property
    def model_version(self) -> str | None:
        return self._version

    def maybe_reload(self) -> bool:
        with self._lock:
            try:
                stat = self.path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                self._clear("artifact not found")
                return False
            if self._model is not None and stamp == self._stamp:
                return True
            try:
                self._load(stamp)
            except Exception as exc:  # A malformed deployment artifact must fail closed.
                self._clear(f"invalid artifact: {exc}")
                return False
            return True

    def predict(self, feature_rows: np.ndarray) -> GeoV2Prediction:
        if not self.maybe_reload():
            return GeoV2Prediction("model_unavailable", None, None, self._error)
        values = np.asarray(feature_rows, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != len(self._feature_order) or not np.isfinite(values).all():
            return GeoV2Prediction("model_unavailable", self._version, None, "invalid inference features")
        assert self._model is not None and self._mean is not None and self._scale is not None
        with self._lock, torch.no_grad():
            tensor = torch.from_numpy((values - self._mean) / self._scale)
            probabilities = self._model.predict_proba(tensor).cpu().numpy()
        return GeoV2Prediction(
            "ok", self._version,
            [{label: float(row[index]) for index, label in enumerate(self._labels)} for row in probabilities],
        )

    def _load(self, stamp: tuple[int, int]) -> None:
        payload = torch.load(self.path, map_location="cpu", weights_only=False)
        if not isinstance(payload, dict):
            raise ValueError("checkpoint must be a metadata dictionary")
        order = tuple(payload.get("ordered_feature_names", payload.get("feature_order", ())))
        expected = tuple(FEATURE_VARIANTS["history_spatial"])
        if order != expected:
            raise ValueError("feature_order must exactly match history_spatial")
        reject_forbidden_columns(order, context="artifact feature_order")
        scaler = payload.get("scaler") or {
            "mean": payload.get("scaler_mean", payload.get("mean")),
            "scale": payload.get("scaler_scale", payload.get("scale")),
        }
        mean, scale = scaler.get("mean"), scaler.get("scale")
        if isinstance(mean, dict) and isinstance(scale, dict):
            if tuple(mean) != order or tuple(scale) != order:
                raise ValueError("scaler keys must exactly match feature_order")
            mean_array = np.asarray([mean[name] for name in order], dtype=np.float32)
            scale_array = np.asarray([scale[name] for name in order], dtype=np.float32)
        elif isinstance(mean, (list, tuple)) and isinstance(scale, (list, tuple)) and len(mean) == len(order) and len(scale) == len(order):
            mean_array = np.asarray(mean, dtype=np.float32)
            scale_array = np.asarray(scale, dtype=np.float32)
        else:
            raise ValueError("scaler must match feature_order")
        if not np.isfinite(mean_array).all() or not np.isfinite(scale_array).all() or (scale_array <= 0).any():
            raise ValueError("scaler values must be finite with positive scale")
        raw_labels = payload.get("label_mapping", payload.get("labels", DEFAULT_LABELS))
        if isinstance(raw_labels, dict):
            if set(raw_labels) != set(DEFAULT_LABELS) or set(raw_labels.values()) != set(range(len(DEFAULT_LABELS))):
                raise ValueError("label mapping must contain each canonical label exactly once")
            labels = tuple(name for name, _ in sorted(raw_labels.items(), key=lambda item: item[1]))
        else:
            labels = tuple(raw_labels)
            if len(labels) != len(DEFAULT_LABELS) or set(labels) != set(DEFAULT_LABELS):
                raise ValueError("labels must contain each canonical label exactly once")
        state = payload.get("model_state_dict", payload.get("state_dict"))
        if not isinstance(state, dict):
            raise ValueError("model_state_dict is required")
        model = GeoV2MLP(
            len(order), int(payload.get("hidden_size", 64)), len(labels), float(payload.get("dropout_rate", 0.2)),
        )
        model.load_state_dict(state, strict=True)
        model.eval()
        self._model, self._feature_order = model, order
        self._mean, self._scale, self._labels = mean_array, scale_array, labels
        self._version = str(payload.get("model_version") or payload.get("version") or f"mtime-{stamp[0]}")
        self._stamp, self._error = stamp, None

    def _clear(self, error: str) -> None:
        self._model = None
        self._feature_order = ()
        self._mean = self._scale = None
        self._labels = ()
        self._version = None
        self._stamp = None
        self._error = error


GEO_V2_MODEL_STORE = GeoV2ModelStore()
