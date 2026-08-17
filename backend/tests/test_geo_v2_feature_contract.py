from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.ml.geo_v2.feature_contract import build_feature_trace
from app.ml.geo_v2.features import CausalFeatureBuilder
from app.services.geo_v2.runtime_inference import GeoV2Context, GeoV2Telemetry, _build_trace


def _telemetry(speed: float, count: float = 12) -> GeoV2Telemetry:
    return GeoV2Telemetry(speed, 3, count, 0.3, 90, 0.1)


def _row(at: datetime, speed: float, count: float = 12) -> dict[str, float]:
    return {"_timestamp": at.timestamp(), "avg_speed_kmph": speed, "vehicle_count": count}


def _context(at: datetime, neighbors=()) -> GeoV2Context:
    return GeoV2Context(
        "source", "run", "segment", at, _telemetry(20, 15), "arterial", 2, 40,
        30, 3, 10, tuple(neighbors), (),
    )


def test_shared_training_runtime_feature_trace_parity():
    at = datetime(2026, 8, 17, 8, 6)
    prior = [_row(at - timedelta(seconds=120 * slot), speed) for slot, speed in ((1, 18), (2, 21), (3, 24))]
    context = _context(at, (_telemetry(16, 9),))
    runtime = _build_trace(context, prior)
    shared = build_feature_trace(
        timestamp=at, current=context.telemetry.__dict__, road_type="arterial", lane_count=2,
        max_speed_kmph=40, baseline_speed_kmph=30, baseline_speed_std_kmph=3,
        baseline_vehicle_count=10, prior_rows=prior, neighbors=[context.neighbors[0].__dict__],
    )
    assert runtime == shared
    assert runtime["prior_speed_mean_3"] == pytest.approx(21)


def test_history_requires_exact_120_second_slots_and_fills_missing_with_baseline():
    at = datetime(2026, 8, 17, 8, 6)
    prior = [
        _row(at - timedelta(seconds=120), 18),
        _row(at - timedelta(seconds=240), 21),
        _row(at - timedelta(seconds=300), 1),  # Delayed/non-slot row is ignored.
    ]
    trace = _build_trace(_context(at), prior)
    assert trace["prior_speed_mean_3"] == pytest.approx((18 + 21 + 30) / 3)
    assert trace["history_observed_slots"] == 2


def test_duplicate_history_tick_is_deterministically_replaced_by_latest_value():
    at = datetime(2026, 8, 17, 8, 6)
    prior = [_row(at - timedelta(seconds=120), 99), _row(at - timedelta(seconds=120), 18)]
    trace = _build_trace(_context(at), prior)
    assert trace["prior_speed_mean_3"] == pytest.approx((18 + 30 + 30) / 3)
    assert trace["history_observed_slots"] == 1


def test_offline_builder_rejects_noncanonical_history_cadence():
    import pandas as pd

    class _Network:
        transitions = ()

    states = pd.DataFrame([
        {"segment_id": "s1", "region_id": "REGION_01", "timestamp": datetime(2026, 8, 17, 8, 0), "avg_speed_kmph": 30, "speed_std_kmph": 3, "vehicle_count": 10, "occupancy": 0.2, "flow_rate_vph": 60, "stopped_fraction": 0, "road_type_code": 2, "lane_count": 2, "max_speed_kmph": 40, "is_prehistory": True},
        {"segment_id": "s1", "region_id": "REGION_01", "timestamp": datetime(2026, 8, 17, 8, 5), "avg_speed_kmph": 20, "speed_std_kmph": 3, "vehicle_count": 12, "occupancy": 0.3, "flow_rate_vph": 90, "stopped_fraction": 0, "road_type_code": 2, "lane_count": 2, "max_speed_kmph": 40, "is_prehistory": False},
    ])
    baselines = pd.DataFrame([{"segment_id": "s1", "baseline_speed_kmph": 30, "baseline_speed_std_kmph": 3, "baseline_vehicle_count": 10}])
    with pytest.raises(ValueError, match="120-second cadence"):
        CausalFeatureBuilder(_Network()).build(states, baselines, variant="history_current")
