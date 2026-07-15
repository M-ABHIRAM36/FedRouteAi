"""
Behavioral Signature Extractor
---------------------------------
Turns a window of recent GPS pings on a segment into a "signature":
how far current speed/density/u-turn-rate/variance deviate from that
segment's OWN historical baseline at this hour. This signature is what
gets compared against the EVENT_SIGNATURES patterns.
"""
from dataclasses import dataclass

from app.models.gps_ping import GPSPing
from app.models.historical_memory import HistoricalMemory


@dataclass
class BehavioralSignature:
    segment_id: str
    speed_ratio: float      # current_avg_speed / baseline_avg_speed
    density_ratio: float    # current_vehicle_count / baseline_avg_vehicle_count
    uturn_ratio: float      # current_uturn_rate / baseline_uturn_rate (baseline floor applied)
    variance_ratio: float   # current_speed_std / baseline_speed_std
    sample_size: int


def extract_signature(
    recent_pings: list[GPSPing],
    baseline: HistoricalMemory,
    window_minutes: float = 20.0,
) -> BehavioralSignature | None:
    if not recent_pings:
        return None

    speeds = [p.speed_kmph for p in recent_pings]
    vehicle_ids = {p.vehicle_id for p in recent_pings}
    uturns = sum(1 for p in recent_pings if p.is_uturn_flag)

    cur_avg_speed = sum(speeds) / len(speeds)
    cur_variance = sum((s - cur_avg_speed) ** 2 for s in speeds) / max(len(speeds) - 1, 1)
    cur_std = cur_variance ** 0.5
    cur_uturn_rate = uturns / len(recent_pings)

    # baseline.avg_vehicle_count is a PER-HOUR figure (see aggregator.py);
    # scale it down to match however long the live window actually is,
    # otherwise a short window always looks artificially "quiet" and a
    # long one always looks artificially "dense".
    expected_count_for_window = baseline.avg_vehicle_count * (window_minutes / 60.0)

    # small floors to avoid divide-by-zero on quiet baselines
    baseline_speed = max(baseline.avg_speed_kmph, 1.0)
    baseline_density = max(expected_count_for_window, 0.5)
    baseline_uturn = max(baseline.uturn_rate, 0.01)
    baseline_std = max(baseline.std_speed_kmph, 0.5)

    return BehavioralSignature(
        segment_id=baseline.segment_id,
        speed_ratio=round(cur_avg_speed / baseline_speed, 3),
        density_ratio=round(len(vehicle_ids) / baseline_density, 3),
        uturn_ratio=round(cur_uturn_rate / baseline_uturn, 3),
        variance_ratio=round(cur_std / baseline_std, 3),
        sample_size=len(recent_pings),
    )
