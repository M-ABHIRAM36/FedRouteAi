from dataclasses import fields

import numpy as np
import pytest

from app.ml.features.windowing import FEATURE_COLUMNS
from app.services.geo_v2.inference import (
    HistoricalBaseline,
    NeighborAggregate,
    SegmentContext,
    TelemetryAggregate,
    build_feature_vector,
    infer_telemetry_state,
)


class _Predictor:
    def __init__(self, trained: bool = True):
        self.is_trained = trained
        self.round_number = 7
        self.calls = 0

    def predict(self, features: np.ndarray):
        self.calls += 1
        return {"normal": 0.2, "construction": 0.8}


def _inputs():
    telemetry = TelemetryAggregate(
        avg_speed_kmph=20.0,
        vehicle_count=8,
        uturn_rate=0.1,
        std_speed_kmph=6.0,
    )
    baseline = HistoricalBaseline(
        avg_speed_kmph=40.0,
        std_speed_kmph=3.0,
        avg_vehicle_count=12.0,
        uturn_rate=0.05,
        sample_size=500,
    )
    segment = SegmentContext(hour_of_day=12, road_type="arterial", lane_count=4, flood_prone=False)
    neighbors = [NeighborAggregate(speed_ratio=0.6, density_ratio=1.5)]
    return telemetry, baseline, segment, neighbors


def test_feature_builder_produces_exact_canonical_ten_dimensions():
    features = build_feature_vector(*_inputs())

    assert features.shape == (10,)
    assert features.dtype == np.float32
    assert len(FEATURE_COLUMNS) == len(features)
    assert features.tolist() == pytest.approx([0.5, 2.0, 2.0, 2.0, 0.5, 2, 4, 0, 0.6, 1.5])


def test_feature_contract_cannot_accept_scenario_or_ground_truth():
    names = {field.name for field in fields(TelemetryAggregate)}
    assert "scenario" not in names
    assert "ground_truth" not in names

    with pytest.raises(TypeError):
        TelemetryAggregate(
            avg_speed_kmph=20,
            vehicle_count=4,
            uturn_rate=0,
            std_speed_kmph=1,
            ground_truth="construction",
        )


def test_historical_memory_changes_ratio_features():
    telemetry, baseline, segment, neighbors = _inputs()
    original = build_feature_vector(telemetry, baseline, segment, neighbors)
    slower_baseline = HistoricalBaseline(
        avg_speed_kmph=20.0,
        std_speed_kmph=baseline.std_speed_kmph,
        avg_vehicle_count=6.0,
        uturn_rate=baseline.uturn_rate,
        sample_size=baseline.sample_size,
    )
    changed = build_feature_vector(telemetry, slower_baseline, segment, neighbors)

    assert original[0] == pytest.approx(0.5)
    assert changed[0] == pytest.approx(1.0)
    assert original[1] == pytest.approx(2.0)
    assert changed[1] == pytest.approx(4.0)


def test_untrained_model_returns_state_without_calling_predictor():
    predictor = _Predictor(trained=False)
    result = infer_telemetry_state(*_inputs(), predictor=predictor)

    assert result.model_version == "federated-round-7"
    assert result.prediction is None
    assert result.confidence is None
    assert result.probabilities == {}
    assert result.baseline["sample_size"] == 500
    assert result.deviations["speed_ratio"] == pytest.approx(0.5)
    assert predictor.calls == 0


def test_probability_predictor_returns_full_distribution():
    result = infer_telemetry_state(*_inputs(), predictor=_Predictor())

    assert result.prediction == "construction"
    assert result.confidence == pytest.approx(0.8)
    assert result.probabilities == {"normal": 0.2, "construction": 0.8}
