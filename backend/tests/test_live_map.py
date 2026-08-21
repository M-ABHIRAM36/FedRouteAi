from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

import pytest

from app.models.region import Region
from app.models.segment import Segment
from app.services.live_simulation import LiveTrafficSimulation, SimulationConfig


GENERATOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "dataset_generator"
sys.path.insert(0, str(GENERATOR_DIR))
from road_network import build_road_network  # noqa: E402


def _seed_network(session_factory, rows) -> None:
    db = session_factory()
    try:
        region_ids = sorted({str(row.region_id) for row in rows})
        db.add_all([
            Region(
                region_id=region_id,
                pincode=500001 + index,
                center_lat=17.385,
                center_lon=78.4867,
                segment_count=sum(row.region_id == region_id for row in rows),
            )
            for index, region_id in enumerate(region_ids)
        ])
        db.add_all([
            Segment(
                segment_id=str(row.segment_id), road_name=str(row.road_name), road_type=str(row.road_type),
                region_id=str(row.region_id), pincode=int(row.pincode), start_lat=float(row.start_lat),
                start_lon=float(row.start_lon), end_lat=float(row.end_lat), end_lon=float(row.end_lon),
                segment_length_m=float(row.segment_length_m), number_of_lanes=int(row.number_of_lanes),
                road_width_m=float(row.road_width_m), max_speed_kmph=float(row.max_speed_kmph),
                road_direction=str(row.road_direction), flood_prone=bool(row.flood_prone),
                neighbor_segments=str(row.neighbor_segments),
            )
            for row in rows
        ])
        db.commit()
    finally:
        db.close()


def _payload(batch: list[dict], tick: int, run_id: str) -> dict:
    return {
        "source_id": "map-test-simulator",
        "run_id": run_id,
        "batch_id": f"tick-{tick}",
        "tick_number": tick,
        "observations": [{
            "observation_id": f"{tick}:{row['vehicle_id']}",
            **row,
            "timestamp": row["timestamp"].isoformat(),
        } for row in batch],
    }


@pytest.fixture()
def live_map_client(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.live_ingest.settings.LIVE_INGEST_API_KEY", "map-secret")
    return client


def test_snapshot_returns_latest_real_vehicle_positions_and_events(live_map_client):
    from app.db.session import SessionLocal

    segments, _ = build_road_network(seed=42)
    rows = list(segments.itertuples(index=False))
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=100, random_seed=42))
    simulation.start()
    event_segment = max(
        simulation.state.road_segment_states,
        key=lambda segment_id: simulation.state.road_segment_states[segment_id].vehicle_count,
    )
    simulation.add_event("accident", event_segment, duration_minutes=30)

    first = simulation.tick()
    second = simulation.tick()
    for tick, batch in enumerate((first, second), start=1):
        response = live_map_client.post(
            "/api/v1/ingest/live/batch",
            json=_payload(batch, tick, "latest-run"),
            headers={"X-Live-Ingest-Key": "map-secret"},
        )
        assert response.status_code == 200, response.text

    response = live_map_client.get("/api/v1/live-map/snapshot")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["source_id"] == "map-test-simulator"
    assert snapshot["run_id"] == "latest-run"
    assert snapshot["tick_number"] == 2
    assert snapshot["summary"]["vehicle_count"] == 100
    assert len(snapshot["vehicles"]) == 100
    assert len({vehicle["vehicle_id"] for vehicle in snapshot["vehicles"]}) == 100
    assert all(vehicle["timestamp"] == second[0]["timestamp"].isoformat() for vehicle in snapshot["vehicles"])
    assert snapshot["segments"]
    assert all(state["latest_timestamp"] for state in snapshot["segments"])
    assert snapshot["events"]
    assert all(event["event_type"] == "accident" for event in snapshot["events"])


def test_snapshot_isolates_requested_run_and_excludes_stale_positions(live_map_client):
    from app.db.session import SessionLocal

    segments, _ = build_road_network(seed=42)
    rows = list(segments.itertuples(index=False))
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=5, random_seed=7))
    simulation.start()
    old_batch = simulation.tick()
    latest_batch = simulation.tick()
    for item in old_batch:
        item["timestamp"] = latest_batch[0]["timestamp"] - timedelta(minutes=5)

    for run_id, tick, batch in (("old-run", 1, old_batch), ("new-run", 1, latest_batch)):
        response = live_map_client.post(
            "/api/v1/ingest/live/batch",
            json=_payload(batch, tick, run_id),
            headers={"X-Live-Ingest-Key": "map-secret"},
        )
        assert response.status_code == 200

    old_response = live_map_client.get(
        "/api/v1/live-map/snapshot",
        params={"source_id": "map-test-simulator", "run_id": "old-run"},
    )
    new_response = live_map_client.get(
        "/api/v1/live-map/snapshot",
        params={"source_id": "map-test-simulator", "run_id": "new-run"},
    )
    assert old_response.status_code == 200
    assert old_response.json()["summary"]["vehicle_count"] == 5
    assert new_response.status_code == 200
    assert new_response.json()["run_id"] == "new-run"
    assert new_response.json()["summary"]["vehicle_count"] == 5


def test_latest_restarted_run_replaces_segment_projection(live_map_client):
    from app.db.session import SessionLocal

    segments, _ = build_road_network(seed=42)
    rows = list(segments.itertuples(index=False))
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=100, random_seed=42))
    simulation.start()
    later_batch = simulation.tick()
    restarted_batch = simulation.tick()
    for item in later_batch:
        item["timestamp"] = restarted_batch[0]["timestamp"] + timedelta(minutes=5)

    for run_id, batch in (("older-run", later_batch), ("restarted-run", restarted_batch)):
        response = live_map_client.post(
            "/api/v1/ingest/live/batch",
            json=_payload(batch, 1, run_id),
            headers={"X-Live-Ingest-Key": "map-secret"},
        )
        assert response.status_code == 200

    response = live_map_client.get("/api/v1/live-map/snapshot")
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["run_id"] == "restarted-run"
    assert snapshot["segments"]


def test_current_state_contains_all_130_segments_after_full_tick(live_map_client):
    from app.db.session import SessionLocal

    segments, _ = build_road_network(seed=42)
    rows = list(segments.itertuples(index=False))
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=2000, random_seed=42))
    simulation.start()
    response = live_map_client.post(
        "/api/v1/ingest/live/batch",
        json=_payload(simulation.tick(), 1, "all-segments"),
        headers={"X-Live-Ingest-Key": "map-secret"},
    )
    assert response.status_code == 200

    states = live_map_client.get("/api/v1/ingest/live/current-state")
    assert states.status_code == 200
    assert len(states.json()) == 130


def test_snapshot_returns_404_without_live_data(live_map_client):
    response = live_map_client.get("/api/v1/live-map/snapshot")
    assert response.status_code == 404
    assert response.json()["detail"] == "no live ingestion batch is available"
