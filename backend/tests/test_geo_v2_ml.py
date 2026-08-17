from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.ml.geo_v2.audit import audit_split_episode_leakage
from app.ml.geo_v2.dataset import GeoV2DatasetBuilder
from app.ml.geo_v2.features import (
    CURRENT_ONLY, FEATURE_VARIANTS, HISTORY, SPATIAL, CausalFeatureBuilder,
    TrainScaler, reject_forbidden_columns,
)
from app.services.geo_v2.network import normalize_overpass_json


@pytest.fixture
def ml_network():
    points = {1: (17.0, 78.0), 2: (17.0, 78.001), 3: (17.0, 78.002)}

    def way(way_id: int, nodes: list[int]):
        return {
            "type": "way", "id": way_id, "nodes": nodes,
            "geometry": [{"lat": points[node][0], "lon": points[node][1]} for node in nodes],
            "tags": {"highway": "primary", "oneway": "yes", "lanes": "2", "maxspeed": "40"},
        }

    return normalize_overpass_json({"elements": [way(1, [1, 2]), way(2, [2, 3])]})


@pytest.fixture
def traffic_fixture(ml_network):
    start = datetime(2026, 7, 1, 6)
    rows = []
    for tick in range(6):
        for segment_index, segment in enumerate(ml_network.segments):
            rows.append({
                "segment_id": segment.segment_id, "region_id": segment.region_id,
                "timestamp": start + timedelta(minutes=2 * tick),
                "avg_speed_kmph": 30.0 - tick - segment_index,
                "speed_std_kmph": 2.0 + segment_index, "vehicle_count": 5 + tick + segment_index,
                "occupancy": 0.2 + tick / 100, "flow_rate_vph": 30.0 + tick,
                "stopped_fraction": 0.0, "road_type_code": 2,
                "lane_count": 2, "max_speed_kmph": 40.0, "is_prehistory": tick < 2,
            })
    states = pd.DataFrame(rows)
    baselines = pd.DataFrame([{
        "segment_id": segment.segment_id, "baseline_speed_kmph": 30.0,
        "baseline_speed_std_kmph": 2.0, "baseline_vehicle_count": 6.0,
    } for segment in ml_network.segments])
    return states, baselines


def test_feature_variants_are_explicit_ordered_prefixes():
    assert FEATURE_VARIANTS["current_only"] == CURRENT_ONLY
    assert FEATURE_VARIANTS["history_current"] == CURRENT_ONLY + HISTORY
    assert FEATURE_VARIANTS["history_spatial"] == CURRENT_ONLY + HISTORY + SPATIAL
    assert len(CURRENT_ONLY) == 11


def test_future_rows_cannot_change_earlier_features(ml_network, traffic_fixture):
    states, baselines = traffic_fixture
    builder = CausalFeatureBuilder(ml_network)
    original = builder.build(states, baselines, variant="history_spatial")
    changed = states.copy()
    latest = changed["timestamp"].max()
    changed.loc[changed["timestamp"] == latest, ["avg_speed_kmph", "vehicle_count"]] = [999.0, 999]
    rebuilt = builder.build(changed, baselines, variant="history_spatial")
    pd.testing.assert_frame_equal(
        original[original["timestamp"] < latest].reset_index(drop=True),
        rebuilt[rebuilt["timestamp"] < latest].reset_index(drop=True),
    )


def test_neighbor_features_use_only_observed_directed_neighbor(ml_network, traffic_fixture):
    states, baselines = traffic_fixture
    source = ml_network.transitions[0].from_segment_id
    target = ml_network.transitions[0].to_segment_id
    timestamp = states["timestamp"].max()
    built = CausalFeatureBuilder(ml_network).build(states, baselines, variant="history_spatial")
    source_row = built[(built["segment_id"] == source) & (built["timestamp"] == timestamp)].iloc[0]
    target_speed = states[(states["segment_id"] == target) & (states["timestamp"] == timestamp)]["avg_speed_kmph"].iloc[0]
    assert source_row["neighbor_speed_mean"] == target_speed
    without_observation = states[~((states["segment_id"] == target) & (states["timestamp"] == timestamp))]
    rebuilt = CausalFeatureBuilder(ml_network).build(without_observation, baselines, variant="history_spatial")
    source_row = rebuilt[(rebuilt["segment_id"] == source) & (rebuilt["timestamp"] == timestamp)].iloc[0]
    assert source_row["observed_neighbor_count"] == 0
    assert source_row["neighbor_speed_mean"] == 0


def test_split_and_episode_leakage_audit_detects_both_failures():
    table = pd.DataFrame({
        "episode_id": ["E1", "E1"], "split": ["train", "validation"],
        "timestamp": [datetime(2026, 1, 2), datetime(2026, 1, 1)],
    })
    errors = audit_split_episode_leakage(table)
    assert any("episodes cross splits" in error for error in errors)
    assert any("timestamp overlap" in error for error in errors)


def test_scaler_is_fit_on_train_only():
    train = pd.DataFrame({"x": [0.0, 2.0]})
    validation = pd.DataFrame({"x": [101.0]})
    scaler = TrainScaler.fit(train, ["x"])
    transformed = scaler.transform(validation, ["x"])
    assert scaler.mean["x"] == 1.0
    assert transformed.loc[0, "x"] == 100.0


@pytest.mark.parametrize("column", ["label", "event_id", "scenario_type", "vehicle_id", "ground_truth"])
def test_forbidden_feature_rejection(column):
    with pytest.raises(ValueError, match="forbidden columns"):
        reject_forbidden_columns(["avg_speed_kmph", column])


def test_feature_and_dataset_construction_are_reproducible(ml_network, traffic_fixture):
    states, baselines = traffic_fixture
    split_states = {name: states.assign(timestamp=states["timestamp"] + timedelta(days=index * 10)) for index, name in enumerate(("train", "validation", "test"))}
    split_baselines = {name: baselines.copy() for name in split_states}
    truths = {name: pd.DataFrame(columns=["event_type", "event_id", "segment_id", "start_time", "end_time"]) for name in split_states}
    builder = GeoV2DatasetBuilder(ml_network)
    first = builder.build(split_states, split_baselines, truths)
    second = builder.build(split_states, split_baselines, truths)
    for variant in FEATURE_VARIANTS:
        pd.testing.assert_frame_equal(first.tables[variant], second.tables[variant])
        assert first.scalers[variant].as_dict() == second.scalers[variant].as_dict()
