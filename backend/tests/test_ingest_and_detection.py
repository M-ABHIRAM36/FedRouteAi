"""
End-to-end integration test: seed a tiny road network + a historical
baseline directly into the test DB, POST a GPS batch that looks like
congestion (slow, dense) on that segment, and confirm the background
detection task actually writes an Event row that GET /events then
returns — this is the full ingest -> detect -> serve loop, not just
each piece in isolation.
"""
import time
from datetime import timedelta

from app.utils.time_utils import utcnow

from app.models.region import Region
from app.models.segment import Segment
from app.models.historical_memory import HistoricalMemory
from app.models.gps_ping import GPSPing


def _seed_minimal_network(session_factory):
    db = session_factory()
    try:
        db.add(Region(region_id="REGION_TEST", pincode=500001, center_lat=17.3850, center_lon=78.4867, segment_count=1))
        db.add(Segment(
            segment_id="TEST_SEG_01", road_name="Test Road", road_type="collector",
            region_id="REGION_TEST", pincode=500001,
            start_lat=17.3850, start_lon=78.4867, end_lat=17.3860, end_lon=78.4867,
            segment_length_m=111.0, number_of_lanes=2, road_width_m=8.0, max_speed_kmph=45.0,
            road_direction="bidirectional", flood_prone=False, neighbor_segments="",
        ))
        now_hour = utcnow().hour
        db.add(HistoricalMemory(
            segment_id="TEST_SEG_01", hour_of_day=now_hour,
            avg_speed_kmph=40.0, std_speed_kmph=4.0, avg_vehicle_count=5.0,
            uturn_rate=0.02, sample_size=200,
        ))
        db.commit()
    finally:
        db.close()


def test_ingest_triggers_detection_and_event_is_servable(client, monkeypatch):
    from app.db.session import SessionLocal as TestSessionLocal
    _seed_minimal_network(TestSessionLocal)

    now = utcnow()
    # Calibrated to congestion's actual target signature (see
    # event_signatures.py: speed x0.55, density x1.8): baseline is 6
    # vehicles/hr (~2 in a 20-min window) at 40kmph, so ~4 vehicles at
    # ~22kmph is a realistic congestion-like read.
    #
    # One POST per vehicle, matching real usage: a batch is ONE device's
    # trajectory (GPSBatchIn.device_id is singular by design), not a
    # grab-bag of unrelated vehicles — four separate phones sending their
    # own batches is what "four vehicles" actually looks like on the wire.
    speeds = [20.0, 22.0, 24.0, 23.0]
    total_matched = 0
    for i, speed in enumerate(speeds):
        resp = client.post("/api/v1/ingest/gps", json={
            "device_id": f"veh_{i}",
            "pings": [{
                "lat": 17.3855, "lon": 78.4867, "speed_kmph": speed,
                "heading_deg": 0, "timestamp": (now - timedelta(minutes=1)).isoformat(),
            }],
        })
        assert resp.status_code == 202
        total_matched += resp.json()["matched"]

    assert total_matched == 4

    # background task runs in-process after each response for TestClient
    time.sleep(0.2)
    events_resp = client.get("/api/v1/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 1
    assert events[0]["segment_id"] == "TEST_SEG_01"
    assert events[0]["event"] == "congestion"
    assert events[0]["confidence"] >= 0.70
