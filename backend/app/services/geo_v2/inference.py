"""Database-free telemetry feature construction and model inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Protocol, Sequence

import numpy as np

from app.ml.features.windowing import FEATURE_COLUMNS, ROAD_TYPE_ORDINAL


@dataclass(frozen=True, slots=True)
class TelemetryAggregate:
    avg_speed_kmph: float
    vehicle_count: int
    uturn_rate: float
    std_speed_kmph: float
    window_minutes: float = 20.0


@dataclass(frozen=True, slots=True)
class HistoricalBaseline:
    avg_speed_kmph: float
    std_speed_kmph: float
    avg_vehicle_count: float
    uturn_rate: float
    sample_size: int


@dataclass(frozen=True, slots=True)
class SegmentContext:
    hour_of_day: int
    road_type: str
    lane_count: int
    flood_prone: bool


@dataclass(frozen=True, slots=True)
class NeighborAggregate:
    speed_ratio: float
    density_ratio: float


@dataclass(frozen=True, slots=True)
class InferenceResult:
    model_version: str
    prediction: str | None
    confidence: float | None
    probabilities: dict[str, float]
    baseline: dict[str, float | int]
    deviations: dict[str, float]


class Predictor(Protocol):
    is_trained: bool

    def predict(
        self, features: np.ndarray
    ) -> Mapping[str, float] | tuple[str, float] | None: ...


def build_feature_vector(
    telemetry: TelemetryAggregate,
    baseline: HistoricalBaseline,
    segment: SegmentContext,
    neighbors: Sequence[NeighborAggregate] = (),
) -> np.ndarray:
    """Build the canonical 10-D inference vector without labels or scenarios."""
    if telemetry.window_minutes <= 0:
        raise ValueError("window_minutes must be positive")
    if not 0 <= segment.hour_of_day <= 23:
        raise ValueError("hour_of_day must be between 0 and 23")

    expected_vehicles = baseline.avg_vehicle_count * (telemetry.window_minutes / 60.0)
    speed_ratio = round(telemetry.avg_speed_kmph / max(baseline.avg_speed_kmph, 1.0), 3)
    density_ratio = round(telemetry.vehicle_count / max(expected_vehicles, 0.5), 3)
    uturn_ratio = round(telemetry.uturn_rate / max(baseline.uturn_rate, 0.01), 3)
    variance_ratio = round(telemetry.std_speed_kmph / max(baseline.std_speed_kmph, 0.5), 3)

    if neighbors:
        neighbor_avg_speed = round(sum(item.speed_ratio for item in neighbors) / len(neighbors), 3)
        neighbor_density = round(sum(item.density_ratio for item in neighbors) / len(neighbors), 3)
    else:
        neighbor_avg_speed = 0.0
        neighbor_density = 0.0

    features = np.array(
        [
            speed_ratio,
            density_ratio,
            uturn_ratio,
            variance_ratio,
            segment.hour_of_day / 24.0,
            ROAD_TYPE_ORDINAL.get(segment.road_type.lower(), 0),
            segment.lane_count,
            int(segment.flood_prone),
            neighbor_avg_speed,
            neighbor_density,
        ],
        dtype=np.float32,
    )
    if features.shape != (len(FEATURE_COLUMNS),):
        raise RuntimeError("inference feature vector does not match the trained model contract")
    return features


def infer_telemetry_state(
    telemetry: TelemetryAggregate,
    baseline: HistoricalBaseline,
    segment: SegmentContext,
    neighbors: Sequence[NeighborAggregate],
    predictor: Predictor,
    model_version: str | None = None,
) -> InferenceResult:
    """Derive features and invoke an injected, already-trained predictor."""
    features = build_feature_vector(telemetry, baseline, segment, neighbors)
    version = model_version or _model_version(predictor)
    deviations = dict(zip(FEATURE_COLUMNS, (float(value) for value in features), strict=True))

    if not predictor.is_trained:
        return InferenceResult(
            model_version=version,
            prediction=None,
            confidence=None,
            probabilities={},
            baseline=asdict(baseline),
            deviations=deviations,
        )

    raw_prediction = predictor.predict(features)
    if raw_prediction is None:
        prediction = None
        confidence = None
        probabilities: dict[str, float] = {}
    elif isinstance(raw_prediction, Mapping):
        probabilities = {str(label): float(probability) for label, probability in raw_prediction.items()}
        prediction = max(probabilities, key=probabilities.get) if probabilities else None
        confidence = probabilities[prediction] if prediction is not None else None
    else:
        prediction, confidence = str(raw_prediction[0]), float(raw_prediction[1])
        probabilities = {}

    return InferenceResult(
        model_version=version,
        prediction=prediction,
        confidence=confidence,
        probabilities=probabilities,
        baseline=asdict(baseline),
        deviations=deviations,
    )


def _model_version(predictor: Predictor) -> str:
    round_number = getattr(predictor, "round_number", None)
    if round_number is not None:
        return f"federated-round-{round_number}"
    return str(getattr(predictor, "model_version", "unknown"))
