from datetime import timedelta

from app.models.gps_ping import GPSPing
from app.models.event import Event
from app.services.historical_memory.aggregator import build_hourly_profile
from app.services.historical_memory.builder import build_memory_for_segment
from app.utils.time_utils import utcnow


def _ping(segment_id, vehicle_id, speed, ts, uturn=False):
    return GPSPing(
        segment_id=segment_id, region_id="R1", vehicle_id=vehicle_id, vehicle_type="car",
        lat=17.385, lon=78.4867, speed_kmph=speed, heading_deg=0, timestamp=ts,
        is_uturn_flag=uturn, label=None, event_id=None,
    )


def test_avg_vehicle_count_is_per_hour_not_a_multi_day_total():
    """Regression test for a real bug found during development: without
    dividing by the number of distinct days observed, avg_vehicle_count
    silently summed across every day in the lookback window instead of
    representing one hour's typical volume — which broke density_ratio
    comparisons in signature_extractor.py."""
    now = utcnow()
    day1 = [_ping("SEG1", f"d1_v{i}", 40, now) for i in range(4)]
    day2 = [_ping("SEG1", f"d2_v{i}", 40, now - timedelta(days=1)) for i in range(6)]

    profile = build_hourly_profile("SEG1", now.hour, day1 + day2)
    # (4 + 6 distinct vehicles) / 2 distinct days = 5.0 per hour, NOT 10
    assert profile.avg_vehicle_count == 5.0


def test_builder_excludes_pings_during_known_events(db_session):
    now = utcnow()
    hour = now.hour

    # "clean" pings: yesterday, same hour-of-day (falls in the same
    # bucket via lookback_days) but well outside today's event window
    clean_pings = [_ping("SEG1", f"v{i}", 40, now - timedelta(days=1, minutes=i)) for i in range(5)]
    # "contaminated" pings: today, during the event itself
    contaminated_pings = [_ping("SEG1", f"ev_v{i}", 8, now - timedelta(minutes=i)) for i in range(5)]
    db_session.add_all(clean_pings + contaminated_pings)

    db_session.add(Event(
        event_id="EVT_TEST", event_type="congestion", region_id="R1", primary_segment_id="SEG1",
        start_time=now - timedelta(minutes=10), end_time=now + timedelta(minutes=10),
        duration_hours=0, confidence=0.9, severity=0.9, affected_neighbors="", source="detected",
    ))
    db_session.commit()

    written = build_memory_for_segment(db_session, "SEG1", hour, lookback_days=2)
    assert written is True

    from app.repositories.historical_memory_repository import HistoricalMemoryRepository
    baseline = HistoricalMemoryRepository(db_session).get_baseline("SEG1", hour)
    # if contamination leaked in, avg speed would be dragged toward 8 kmph;
    # it should reflect only the clean 40 kmph pings
    assert baseline.avg_speed_kmph == 40.0
