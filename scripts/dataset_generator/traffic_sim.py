"""
traffic_sim.py
---------------
Generates GPS pings for a road network under:
  (a) "normal" conditions — full day/night hourly traffic profile, and
  (b) event conditions — normal profile reshaped by an EVENT_SIGNATURES
      multiplier set for a bounded time window on a bounded set of
      segments.

CONSTRAINTS ENFORCED (so the data can't drift into nonsense):
  - speed_kmph is always clipped to [MIN_SPEED_KMPH, max_speed_kmph*1.15]
  - vehicle count per segment-hour is clipped to a sane [0, cap] range
  - timestamps within one vehicle's trip are strictly increasing
  - GPS points never jitter further off the road centerline than
    (road_width_m/2 + a small GPS-noise margin), converted to lat/lon
    with the correct per-axis meters-to-degrees formula (see geo_utils.py)
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from geo_utils import offset_latlon, interpolate_latlon, bearing_deg
from event_signatures import EVENT_SIGNATURES

MIN_SPEED_KMPH = 4.0
GPS_NOISE_M = 3.0          # typical smartphone GPS accuracy
PING_INTERVAL_S = 4        # one GPS ping every ~4 simulated seconds

VEHICLE_TYPES = ["car", "bike", "auto", "bus"]
VEHICLE_WEIGHTS = [0.50, 0.28, 0.17, 0.05]
VEHICLE_SPEED_ADJUST = {"car": 1.00, "bike": 1.12, "auto": 0.88, "bus": 0.78}


def hourly_profile(hour: int):
    """Returns (speed_multiplier, base_vehicles_per_hour_factor, uturn_base)
    for a given hour of day (0-23). Encodes day/night + peak/off-peak."""
    if 8 <= hour <= 10 or 17 <= hour <= 20:          # morning/evening peak
        return 0.62, 1.7, 0.035
    if 23 <= hour or hour <= 4:                       # deep night
        return 1.08, 0.18, 0.010
    if 5 <= hour <= 7 or 21 <= hour <= 22:            # shoulder hours
        return 0.90, 0.55, 0.018
    return 0.80, 1.0, 0.022                           # normal daytime off-peak


def _vehicle_count_for_hour(base_vehicles_per_hour: float, hour_factor: float,
                             rng: np.random.Generator, cap: int = 60) -> int:
    lam = max(base_vehicles_per_hour * hour_factor, 0.05)
    n = int(rng.poisson(lam))
    return int(np.clip(n, 0, cap))


def _base_vehicles_per_hour(road_type: str) -> float:
    return {"residential": 6, "collector": 14, "arterial": 24, "highway_link": 34}.get(road_type, 10)


def simulate_segment_hour(
    segment: pd.Series,
    timestamp_hour_start: datetime,
    rng: np.random.Generator,
    event: dict | None = None,     # None => normal; else EVENT_SIGNATURES[...] + severity
    is_neighbor_of_event: bool = False,
):
    """Generate all vehicle pings for ONE segment during ONE hour."""
    hour = timestamp_hour_start.hour
    speed_mult, density_factor, uturn_base = hourly_profile(hour)
    base_speed = segment.max_speed_kmph * speed_mult
    base_vph = _base_vehicles_per_hour(segment.road_type)

    speed_variance_mult = 1.0
    density_mult = 1.0
    uturn_mult = 1.0

    if event is not None:
        severity = event.get("severity", 1.0)
        sig = event["signature"]
        # severity blends between "normal" (severity=0) and "full effect" (severity=1)
        speed_mult_eff = 1 + severity * (sig["speed_mult"] - 1)
        density_mult = 1 + severity * (sig["density_mult"] - 1)
        uturn_mult = 1 + severity * (sig["uturn_mult"] - 1)
        speed_variance_mult = 1 + severity * (sig["speed_variance_mult"] - 1)
        base_speed *= speed_mult_eff
    elif is_neighbor_of_event:
        sig = event and event["signature"]
        density_mult = 1.15  # gentle default bump; orchestrator overrides with exact value

    n_vehicles = _vehicle_count_for_hour(base_vph, density_factor * density_mult, rng)
    uturn_prob = np.clip(uturn_base * uturn_mult, 0, 0.9)

    rows = []
    lat1, lon1, lat2, lon2 = segment.start_lat, segment.start_lon, segment.end_lat, segment.end_lon
    half_width = segment.road_width_m / 2.0

    for v in range(n_vehicles):
        vtype = rng.choice(VEHICLE_TYPES, p=VEHICLE_WEIGHTS)
        speed = base_speed * VEHICLE_SPEED_ADJUST[vtype]
        speed *= rng.normal(1.0, 0.10 * speed_variance_mult)
        speed = float(np.clip(speed, MIN_SPEED_KMPH, segment.max_speed_kmph * 1.15))

        travel_time_s = max(segment.segment_length_m / (speed * 1000 / 3600), 3)
        n_pings = max(int(travel_time_s / PING_INTERVAL_S), 2)

        is_uturn = rng.random() < uturn_prob
        fractions = np.linspace(0, 1, n_pings)
        if is_uturn:
            half = max(n_pings // 2, 1)
            fractions = np.concatenate([np.linspace(0, 1, half), np.linspace(1, 0, n_pings - half)])

        start_offset_s = float(rng.uniform(0, 3600))
        vehicle_start_time = timestamp_hour_start + timedelta(seconds=start_offset_s)
        vehicle_id = f"{segment.segment_id}_H{hour:02d}_V{v:03d}"

        for i, frac in enumerate(fractions):
            lat, lon = interpolate_latlon(lat1, lon1, lat2, lon2, float(frac))
            # perpendicular lane jitter, bounded by actual road width + GPS noise
            lateral_m = float(np.clip(rng.normal(0, half_width / 2.2), -half_width, half_width))
            noise_m = float(rng.normal(0, GPS_NOISE_M))
            heading = bearing_deg(lat1, lon1, lat2, lon2) if frac <= 1 else bearing_deg(lat2, lon2, lat1, lon1)
            perp_heading = (heading + 90) % 360
            lat_j, lon_j = offset_latlon(lat, lon, dx_east_m=np.sin(np.radians(perp_heading)) * (lateral_m + noise_m),
                                          dy_north_m=np.cos(np.radians(perp_heading)) * (lateral_m + noise_m))
            ping_time = vehicle_start_time + timedelta(seconds=i * PING_INTERVAL_S)
            rows.append(dict(
                segment_id=segment.segment_id,
                region_id=segment.region_id,
                vehicle_id=vehicle_id,
                vehicle_type=vtype,
                lat=round(lat_j, 7),
                lon=round(lon_j, 7),
                speed_kmph=round(float(np.clip(speed + rng.normal(0, 2.0 * speed_variance_mult), MIN_SPEED_KMPH, segment.max_speed_kmph * 1.2)), 1),
                heading_deg=round(heading, 1),
                timestamp=ping_time,
                is_uturn_flag=bool(is_uturn and i == len(fractions) // 2),
                label=(event["type"] if event is not None else "normal"),
            ))
    return rows
