from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.geo_v2.common import aggregate_observations, scrub_observations
from app.services.live_ingestion.client import LiveIngestionClient


def test_scrub_keeps_truth_out_of_live_telemetry():
    rows = [{"segment_id": "s", "vehicle_id": "v", "speed_kmph": 10, "label": "flood", "event_id": "E1"}]
    clean = scrub_observations(rows)
    assert clean[0]["label"] == "normal"
    assert clean[0]["event_id"] == ""
    assert rows[0]["event_id"] == "E1"


def test_aggregate_is_label_free_and_deterministic():
    result = aggregate_observations([
        {"segment_id": "s", "vehicle_id": "a", "speed_kmph": 10, "is_uturn_flag": False},
        {"segment_id": "s", "vehicle_id": "b", "speed_kmph": 20, "is_uturn_flag": True},
    ])["s"]
    assert result.vehicle_count == 2
    assert result.avg_speed_kmph == 15
    assert result.uturn_rate == 0.5


def test_live_client_sends_geo_v2_network_identity(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"accepted": 1}

    def post(url, *, json, headers, timeout):
        captured.update(json)
        return Response()

    monkeypatch.setattr("app.services.live_ingestion.client.httpx.post", post)
    client = LiveIngestionClient(
        "http://example.test", "secret", "source", "run",
        network_source="osm_geo_v2", network_version="beeramguda-osm-20260506",
    )
    client.ingest(1, [{
        "vehicle_id": "v", "segment_id": "s", "region_id": "REGION_01",
        "vehicle_type": "car", "lat": 17.5, "lon": 78.3, "speed_kmph": 20,
        "heading_deg": 0, "timestamp": datetime(2026, 1, 1), "is_uturn_flag": False,
        "label": "normal", "event_id": "",
    }])
    assert captured["network_source"] == "osm_geo_v2"
    assert captured["network_version"] == "beeramguda-osm-20260506"
