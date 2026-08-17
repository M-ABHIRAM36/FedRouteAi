"""Pure Geo V2 raw-feature contract shared by training checks and runtime."""
from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Mapping, Sequence


FEATURE_CONTRACT_VERSION = "geo-v2-causal-120s-v2"
HISTORY_CADENCE_SECONDS = 120
HISTORY_SLOTS = 3
ROAD_TYPE_CODES = {"residential": 0, "collector": 1, "arterial": 2, "highway_link": 3}


def cadence_history(
    rows: Sequence[Mapping[str, float]], as_of: datetime, baseline_speed: float,
    baseline_count: float,
) -> tuple[list[float], list[float], list[bool]]:
    """Return t-1/t-2/t-3 slots; missing slots use causal baseline fallback."""
    by_timestamp: dict[int, Mapping[str, float]] = {}
    for row in rows:
        timestamp = row.get("_timestamp")
        if timestamp is None:
            continue
        epoch = int(float(timestamp))
        if epoch < int(as_of.timestamp()):
            by_timestamp[epoch] = row
    speeds: list[float] = []
    counts: list[float] = []
    observed: list[bool] = []
    for slot in range(1, HISTORY_SLOTS + 1):
        expected = int((as_of - timedelta(seconds=HISTORY_CADENCE_SECONDS * slot)).timestamp())
        row = by_timestamp.get(expected)
        observed.append(row is not None)
        speeds.append(float(row["avg_speed_kmph"]) if row is not None else baseline_speed)
        counts.append(float(row["vehicle_count"]) if row is not None else baseline_count)
    return speeds, counts, observed


def build_feature_trace(
    *, timestamp: datetime, current: Mapping[str, float], road_type: str,
    lane_count: int, max_speed_kmph: float, baseline_speed_kmph: float,
    baseline_speed_std_kmph: float, baseline_vehicle_count: float,
    prior_rows: Sequence[Mapping[str, float]], neighbors: Sequence[Mapping[str, float]],
) -> dict[str, float]:
    speeds, counts, observed = cadence_history(
        prior_rows, timestamp, baseline_speed_kmph, baseline_vehicle_count,
    )
    prior_speed = sum(speeds) / HISTORY_SLOTS
    prior_count = sum(counts) / HISTORY_SLOTS
    hour = timestamp.hour + timestamp.minute / 60.0
    neighbor_speed = sum(float(row["avg_speed_kmph"]) for row in neighbors) / len(neighbors) if neighbors else 0.0
    neighbor_count = sum(float(row["vehicle_count"]) for row in neighbors) / len(neighbors) if neighbors else 0.0
    neighbor_occupancy = sum(float(row["occupancy"]) for row in neighbors) / len(neighbors) if neighbors else 0.0
    return {
        "avg_speed_kmph": float(current["avg_speed_kmph"]),
        "speed_std_kmph": float(current["speed_std_kmph"]),
        "vehicle_count": float(current["vehicle_count"]), "occupancy": float(current["occupancy"]),
        "flow_rate_vph": float(current["flow_rate_vph"]), "stopped_fraction": float(current["stopped_fraction"]),
        "hour_sin": math.sin(2 * math.pi * hour / 24), "hour_cos": math.cos(2 * math.pi * hour / 24),
        "road_type_code": float(ROAD_TYPE_CODES[road_type.lower()]), "lane_count": float(lane_count),
        "max_speed_kmph": float(max_speed_kmph), "baseline_speed_kmph": float(baseline_speed_kmph),
        "baseline_speed_std_kmph": float(baseline_speed_std_kmph), "baseline_vehicle_count": float(baseline_vehicle_count),
        "speed_to_baseline": float(current["avg_speed_kmph"]) / max(baseline_speed_kmph, 1.0),
        "count_to_baseline": float(current["vehicle_count"]) / max(baseline_vehicle_count, 0.5),
        "std_to_baseline": float(current["speed_std_kmph"]) / max(baseline_speed_std_kmph, 0.5),
        "prior_speed_mean_3": prior_speed, "prior_count_mean_3": prior_count,
        "speed_trend": float(current["avg_speed_kmph"]) - prior_speed,
        "count_trend": float(current["vehicle_count"]) - prior_count,
        "low_speed_persistence_3": sum(speed < 0.7 * baseline_speed_kmph for speed in speeds) / HISTORY_SLOTS,
        "neighbor_speed_mean": neighbor_speed, "neighbor_vehicle_count_mean": neighbor_count,
        "neighbor_occupancy_mean": neighbor_occupancy,
        "neighbor_speed_delta": float(current["avg_speed_kmph"]) - neighbor_speed,
        "observed_neighbor_count": float(len(neighbors)),
        "history_observed_slots": float(sum(observed)),
        "_timestamp": float(timestamp.timestamp()),
    }
