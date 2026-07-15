"""
Historical Road Memory
------------------------
Turns raw (map-matched) GPS pings into the per-segment-per-hour baseline
that everything else compares against. Deliberately simple statistics
(mean/std) for Phase 1 — this is intentional, not a placeholder: you
want an interpretable baseline before reaching for anything fancier,
since the anomaly signal (event_detection/signature_extractor.py) is
just "how far from this baseline are we right now."
"""
from dataclasses import dataclass

from app.models.gps_ping import GPSPing


@dataclass
class HourlyProfile:
    segment_id: str
    hour_of_day: int
    avg_speed_kmph: float
    std_speed_kmph: float
    avg_vehicle_count: float
    uturn_rate: float
    sample_size: int


def build_hourly_profile(segment_id: str, hour_of_day: int, pings: list[GPSPing]) -> HourlyProfile | None:
    """`pings` must already be filtered to (a) this segment, (b) this
    hour-of-day bucket across however many days you're aggregating over,
    and (c) label == 'normal' — feeding it event-contaminated pings will
    poison the baseline it's supposed to detect deviations from."""
    if not pings:
        return None

    speeds = [p.speed_kmph for p in pings]
    uturns = sum(1 for p in pings if p.is_uturn_flag)

    # avg_vehicle_count must be "typical vehicles in ONE occurrence of
    # this hour", not a running total across every day in the lookback
    # window — dividing by the number of distinct calendar days actually
    # represented keeps it on the same scale as a live signature window
    # (see signature_extractor.py, which further scales this down for
    # windows shorter than a full hour).
    vehicle_ids = {p.vehicle_id for p in pings}
    distinct_days = {p.timestamp.date() for p in pings} or {None}

    avg_speed = sum(speeds) / len(speeds)
    variance = sum((s - avg_speed) ** 2 for s in speeds) / max(len(speeds) - 1, 1)

    return HourlyProfile(
        segment_id=segment_id,
        hour_of_day=hour_of_day,
        avg_speed_kmph=round(avg_speed, 1),
        std_speed_kmph=round(variance ** 0.5, 2),
        avg_vehicle_count=round(len(vehicle_ids) / len(distinct_days), 2),
        uturn_rate=round(uturns / len(pings), 3),
        sample_size=len(pings),
    )


# TODO: add a rolling/incremental update path (e.g. exponential moving
# average) so memory can update from streaming pings instead of being
# fully recomputed in batch every time — batch recompute is fine for
# Phase 1 / the synthetic dataset, but won't scale to live ingestion.
