from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.core.constants import EventType, VehicleType
from app.models.gps_ping import GPSPing
from app.models.live_ingestion import LiveIngestionBatch, SegmentCurrentState
from app.models.region import Region
from app.models.segment import Segment
from app.schemas.gps_ping import LiveGPSBatchIn, LiveGPSObservationIn
from app.services.live_ingestion.service import ingest_live_batch
from app.services.live_simulation import LiveTrafficSimulation, SimulationConfig


GENERATOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "dataset_generator"
sys.path.insert(0, str(GENERATOR_DIR))
from road_network import build_road_network  # noqa: E402


def _seed_network(session_factory, segment_rows) -> None:
    db = session_factory()
    try:
        region_ids = sorted({str(row.region_id) for row in segment_rows})
        db.add_all([
            Region(region_id=region_id, pincode=500001 + index, center_lat=17.385, center_lon=78.4867,
                   segment_count=sum(row.region_id == region_id for row in segment_rows))
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
            for row in segment_rows
        ])
        db.commit()
    finally:
        db.close()


def _payload(batch: list[dict], tick: int, run_id: str = "test-run") -> dict:
    return {
        "source_id": "test-simulator",
        "run_id": run_id,
        "batch_id": f"tick-{tick}",
        "tick_number": tick,
        "observations": [
            {
                "observation_id": f"{tick}:{row['vehicle_id']}",
                **row,
                "timestamp": row["timestamp"].isoformat(),
            }
            for row in batch
        ],
    }


def _headers() -> dict[str, str]:
    return {"X-Live-Ingest-Key": "test-secret"}


def _isolated_rows(count: int):
    segments, _ = build_road_network(seed=42)
    return [
        SimpleNamespace(**{**row._asdict(), "neighbor_segments": ""})
        for row in list(segments.head(count).itertuples(index=False))
    ]


@pytest.fixture()
def live_client(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.live_ingest.settings.LIVE_INGEST_API_KEY", "test-secret")
    return client


def test_valid_batch_is_persisted_and_retry_is_idempotent(live_client):
    from app.db.session import SessionLocal

    rows = _isolated_rows(2)
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=20, random_seed=5))
    simulation.start()
    payload = _payload(simulation.tick(), 1)

    response = live_client.post("/api/v1/ingest/live/batch", json=payload, headers=_headers())
    retry = live_client.post("/api/v1/ingest/live/batch", json=payload, headers=_headers())

    assert response.status_code == 200
    assert response.json()["accepted"] == 20
    assert retry.status_code == 200
    assert retry.json()["accepted"] == 0
    assert retry.json()["duplicates"] == 20

    db = SessionLocal()
    try:
        assert db.query(GPSPing).count() == 20
        assert db.query(LiveIngestionBatch).count() == 1
        assert db.query(SegmentCurrentState).count() > 0
    finally:
        db.close()


def test_changed_retry_conflicts(live_client):
    from app.db.session import SessionLocal

    rows = _isolated_rows(1)
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=2, random_seed=1))
    simulation.start()
    payload = _payload(simulation.tick(), 1, "conflict-run")
    assert live_client.post("/api/v1/ingest/live/batch", json=payload, headers=_headers()).status_code == 200
    payload["observations"][0]["speed_kmph"] += 1

    response = live_client.post("/api/v1/ingest/live/batch", json=payload, headers=_headers())
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("change", "expected_status"),
    [
        (lambda item: item.update(segment_id="UNKNOWN"), 422),
        (lambda item: item.update(region_id="REGION_UNKNOWN"), 422),
        (lambda item: item.update(lat=91), 422),
        (lambda item: item.update(lon=181), 422),
        (lambda item: item.update(speed_kmph=-1), 422),
        (lambda item: item.update(label="not_an_event"), 422),
        (lambda item: item.update(label="accident", event_id=""), 422),
    ],
)
def test_invalid_observations_are_rejected(live_client, change, expected_status):
    from app.db.session import SessionLocal

    rows = _isolated_rows(1)
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=1, random_seed=2))
    simulation.start()
    payload = _payload(simulation.tick(), 1, f"invalid-{expected_status}-{id(change)}")
    change(payload["observations"][0])

    response = live_client.post("/api/v1/ingest/live/batch", json=payload, headers=_headers())
    assert response.status_code == expected_status

    db = SessionLocal()
    try:
        assert db.query(GPSPing).count() == 0
    finally:
        db.close()


def test_requires_api_key(live_client):
    response = live_client.post("/api/v1/ingest/live/batch", json={})
    assert response.status_code in {401, 422}


def test_three_1000_ping_ticks_are_chronological_and_update_state(live_client):
    from app.db.session import SessionLocal

    segments, regions = build_road_network(seed=42)
    rows = list(segments.itertuples(index=False))
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=1000, random_seed=42))
    simulation.start()

    timestamps = []
    for tick in range(1, 4):
        batch = simulation.tick()
        response = live_client.post(
            "/api/v1/ingest/live/batch",
            json=_payload(batch, tick, "three-tick-run"),
            headers=_headers(),
        )
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] == 1000
        timestamps.append(batch[0]["timestamp"])

    assert timestamps == sorted(timestamps)
    assert len(regions) == 8
    db = SessionLocal()
    try:
        assert db.query(GPSPing).count() == 3000
        assert db.query(GPSPing.region_id).distinct().count() == 8
        assert db.query(GPSPing.vehicle_id).distinct().count() == 1000
        states = db.query(SegmentCurrentState).all()
        assert states
        assert all(state.latest_timestamp <= timestamps[-1] for state in states)
        assert any(state.latest_timestamp == timestamps[-1] for state in states)
    finally:
        db.close()


def test_current_state_preserves_event_and_availability(live_client):
    from app.db.session import SessionLocal

    rows = _isolated_rows(1)
    _seed_network(SessionLocal, rows)
    simulation = LiveTrafficSimulation(rows, SimulationConfig(pings_per_tick=5, random_seed=3))
    simulation.start()
    simulation.add_event("road_block", rows[0].segment_id, duration_minutes=30)

    response = live_client.post(
        "/api/v1/ingest/live/batch",
        json=_payload(simulation.tick(), 1, "event-run"),
        headers=_headers(),
    )
    state_response = live_client.get(
        "/api/v1/ingest/live/current-state",
        params={"segment_id": rows[0].segment_id},
    )

    assert response.status_code == 200
    assert state_response.status_code == 200
    assert state_response.json()[0]["current_event"] == "road_block"
    assert state_response.json()[0]["available"] is False


def test_service_rolls_back_on_transaction_failure():
    class FailingRepository:
        rolled_back = False

        def get_batch(self, source_id, run_id, batch_id):
            return None

        def segment_regions(self, segment_ids):
            return {"SEG_1": "REGION_01"}

        def persist_batch(self, batch_data, observations, states):
            raise RuntimeError("database failed")

        def rollback(self):
            self.rolled_back = True

    batch = LiveGPSBatchIn(
        source_id="test",
        run_id="rollback",
        batch_id="tick-1",
        tick_number=1,
        observations=[LiveGPSObservationIn(
            observation_id="1:V1",
            segment_id="SEG_1",
            region_id="REGION_01",
            vehicle_id="V1",
            vehicle_type=VehicleType.CAR,
            lat=17.385,
            lon=78.4867,
            speed_kmph=20,
            heading_deg=0,
            timestamp=datetime(2026, 7, 7, 8),
            label=EventType.NORMAL,
        )],
    )
    repository = FailingRepository()

    with pytest.raises(RuntimeError, match="database failed"):
        ingest_live_batch(batch, repository)
    assert repository.rolled_back is True
