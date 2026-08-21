from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

import pytest

from app.services.live_simulation import LiveTrafficSimulation, SimulationConfig
from app.services.map_matching.matcher import _project_point_to_segment_m


GENERATOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "dataset_generator"
sys.path.insert(0, str(GENERATOR_DIR))
from road_network import build_road_network  # noqa: E402


@pytest.fixture(scope="module")
def canonical_segments():
    segments, regions = build_road_network(seed=42)
    assert len(segments) == 130
    assert len(regions) == 8
    return list(segments.itertuples(index=False))


def _simulation(canonical_segments, *, pings: int = 1000, seed: int = 42):
    simulation = LiveTrafficSimulation(
        canonical_segments,
        SimulationConfig(
            pings_per_tick=pings,
            tick_interval_seconds=4.0,
            simulation_speed=1.0,
            random_seed=seed,
        ),
    )
    simulation.start()
    return simulation


def test_tick_emits_existing_schema_on_valid_network(canonical_segments):
    simulation = _simulation(canonical_segments)
    batch = simulation.tick()

    assert len(batch) == 1000
    assert len({row["vehicle_id"] for row in batch}) == 1000
    assert set(batch[0]) == {
        "segment_id", "region_id", "vehicle_id", "vehicle_type", "lat", "lon",
        "speed_kmph", "heading_deg", "timestamp", "is_uturn_flag", "label", "event_id",
    }

    valid_regions = {segment.region_id for segment in simulation.segments.values()}
    for row in batch:
        segment = simulation.segments[row["segment_id"]]
        assert row["region_id"] == segment.region_id
        assert row["region_id"] in valid_regions
        assert _project_point_to_segment_m(row["lat"], row["lon"], segment) < 0.1


def test_vehicle_positions_and_timestamp_evolve_deterministically(canonical_segments):
    first = _simulation(canonical_segments, pings=80, seed=7)
    second = _simulation(canonical_segments, pings=80, seed=7)
    start_time = first.state.current_time
    initial = {
        vehicle_id: (vehicle.segment_id, vehicle.position)
        for vehicle_id, vehicle in first.state.vehicles.items()
    }

    first_batch = first.tick()
    second_batch = second.tick()

    assert first.state.current_time == start_time + timedelta(seconds=4)
    assert first_batch == second_batch
    assert any(
        (vehicle.segment_id, vehicle.position) != initial[vehicle_id]
        for vehicle_id, vehicle in first.state.vehicles.items()
    )


def test_events_change_speed_density_neighbors_and_availability(canonical_segments):
    normal = _simulation(canonical_segments, pings=1000, seed=11)
    affected = _simulation(canonical_segments, pings=1000, seed=11)
    target_id = max(
        affected.state.road_segment_states,
        key=lambda segment_id: affected.state.road_segment_states[segment_id].vehicle_count,
    )
    target = affected.segments[target_id]
    before_density = affected.state.road_segment_states[target_id].density
    normal.tick()

    affected.add_event("congestion", target_id, duration_minutes=60)
    event_batch = affected.tick()
    normal_speeds = [row["speed_kmph"] for row in normal.generate_batch() if row["segment_id"] == target_id]
    event_speeds = [row["speed_kmph"] for row in event_batch if row["segment_id"] == target_id]

    assert event_speeds and normal_speeds
    assert sum(event_speeds) / len(event_speeds) < sum(normal_speeds) / len(normal_speeds)
    assert affected.state.road_segment_states[target_id].density > before_density
    assert affected.state.road_segment_states[target_id].traffic_state == "congestion"
    assert all(row["label"] == "congestion" for row in event_batch if row["segment_id"] == target_id)

    if target.neighbor_ids:
        neighbor_id = target.neighbor_ids[0]
        neighbor_state = affected.state.road_segment_states[neighbor_id]
        assert neighbor_state.density >= neighbor_state.vehicle_count

    affected.remove_event(next(iter(affected.state.active_events)))
    block = affected.add_event("road_block", target_id, duration_minutes=30)
    assert affected.state.road_segment_states[target_id].available is False
    affected.remove_event(block.event_id)
    assert affected.state.road_segment_states[target_id].available is True


def test_runs_ten_ticks_and_reports_requested_metrics(canonical_segments):
    simulation = _simulation(canonical_segments)
    batches = [simulation.tick() for _ in range(10)]
    summary = simulation.summary()

    assert all(len(batch) == 1000 for batch in batches)
    assert simulation.state.tick_number == 10
    assert summary["pings_generated"] == 1000
    assert summary["unique_vehicles"] == 1000
    assert summary["active_road_segments"] > 0
    assert set(summary["region_distribution"]) == {f"REGION_{index:02d}" for index in range(1, 9)}
    assert summary["average_speed_kmph"] > 0
    assert summary["average_density"] > 0


def test_flood_requires_existing_flood_prone_semantics(canonical_segments):
    simulation = _simulation(canonical_segments, pings=10)
    safe_segment = next(segment for segment in simulation.segments.values() if not segment.flood_prone)

    with pytest.raises(ValueError, match="flood-prone"):
        simulation.add_event("flood", safe_segment.segment_id)
