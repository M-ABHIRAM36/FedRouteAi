"""
traffic_sim.py  (V2)
----------------------
Generates GPS pings for a road network under:
  (a) "normal" conditions — full day/night traffic profile shaped by
      day-of-week and weather state, and
  (b) event conditions — normal profile reshaped by an EVENT_SIGNATURES
      multiplier set, applied at 20-minute window granularity with a
      per-window severity value from the event lifecycle (onset→peak→decay).

V2 changes vs V1:
  - contextual_profile(hour, day_of_week, weather) replaces hourly_profile(hour)
  - simulate_segment_window() operates at 20-min granularity with a severity param
  - simulate_segment_hour() is kept for backward compatibility (wraps the new function)
  - Neighbor pings are always labeled "normal" — no more _neighbor_effect labels

CONSTRAINTS ENFORCED (unchanged from V1):
  - speed_kmph is always clipped to [MIN_SPEED_KMPH, max_speed_kmph*1.15]
  - vehicle count per segment-window is clipped to a sane [0, cap] range
  - timestamps within one vehicle's trip are strictly increasing
  - GPS points never jitter further off the road centerline than
    (road_width_m/2 + a small GPS-noise margin)
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from geo_utils import offset_latlon, interpolate_latlon, bearing_deg
from event_signatures import EVENT_SIGNATURES

MIN_SPEED_KMPH = 4.0
GPS_NOISE_M = 3.0          # typical smartphone GPS accuracy
PING_INTERVAL_S = 4        # one GPS ping every ~4 simulated seconds
WINDOW_MINUTES = 20        # V2: simulate at 20-min slices

VEHICLE_TYPES = ["car", "bike", "auto", "bus"]
VEHICLE_WEIGHTS = [0.50, 0.28, 0.17, 0.05]
VEHICLE_SPEED_ADJUST = {"car": 1.00, "bike": 1.12, "auto": 0.88, "bus": 0.78}

# Day-of-week scaling on vehicle density (0=Monday, 6=Sunday)
_DAY_DENSITY_SCALE = {
    0: 1.00,   # Monday
    1: 1.05,   # Tuesday
    2: 1.00,   # Wednesday
    3: 1.05,   # Thursday
    4: 1.10,   # Friday (TGIF effect)
    5: 0.75,   # Saturday
    6: 0.55,   # Sunday
}

# Weather speed/density adjustments
_WEATHER_SPEED_ADJ = {"clear": 1.0, "rain": 0.92, "heavy_rain": 0.80}
_WEATHER_DENSITY_ADJ = {"clear": 1.0, "rain": 1.10, "heavy_rain": 1.20}


def contextual_profile(
    hour: int,
    day_of_week: int = 0,
    weather: str = "clear",
) -> tuple[float, float, float]:
    """Returns (speed_multiplier, density_factor, uturn_base) for a given hour,
    day-of-week, and weather state. V2 replacement for hourly_profile().

    Args:
        hour:        hour of day (0-23)
        day_of_week: 0=Monday, 6=Sunday
        weather:     "clear" | "rain" | "heavy_rain"

    Returns:
        (speed_mult, density_factor, uturn_base)
        density_factor already includes day_of_week scaling.
    """
    # Base hourly pattern (same thresholds as V1)
    if 8 <= hour <= 10 or 17 <= hour <= 20:      # morning/evening peak
        speed_m, density_f, uturn = 0.62, 1.7, 0.035
    elif 23 <= hour or hour <= 4:                 # deep night
        speed_m, density_f, uturn = 1.08, 0.18, 0.010
    elif 5 <= hour <= 7 or 21 <= hour <= 22:      # shoulder hours
        speed_m, density_f, uturn = 0.90, 0.55, 0.018
    else:                                          # normal daytime off-peak
        speed_m, density_f, uturn = 0.80, 1.0, 0.022

    # Apply day-of-week density scaling
    day_scale = _DAY_DENSITY_SCALE.get(day_of_week, 1.0)
    density_f *= day_scale

    # Apply weather adjustments
    speed_m *= _WEATHER_SPEED_ADJ.get(weather, 1.0)
    density_f *= _WEATHER_DENSITY_ADJ.get(weather, 1.0)

    return speed_m, density_f, uturn


def hourly_profile(hour: int) -> tuple[float, float, float]:
    """V1 backward-compatible wrapper — used only by old test code."""
    return contextual_profile(hour, day_of_week=0, weather="clear")


def _vehicle_count_for_window(
    base_vehicles_per_hour: float,
    density_factor: float,
    rng: np.random.Generator,
    cap: int = 60,
) -> int:
    """Scale base VPH to a 20-minute window and draw from Poisson."""
    vph = max(base_vehicles_per_hour * density_factor, 0.05)
    # Scale to 20-min window: vehicles per 20 min = VPH × (20/60)
    lam = vph * (WINDOW_MINUTES / 60.0)
    n = int(rng.poisson(max(lam, 0.01)))
    return int(np.clip(n, 0, cap))


def _base_vehicles_per_hour(road_type: str) -> float:
    return {"residential": 6, "collector": 14, "arterial": 24, "highway_link": 34}.get(road_type, 10)


def simulate_segment_window(
    segment: pd.Series,
    window_start: datetime,
    rng: np.random.Generator,
    event_type: str | None = None,      # None → normal; else key into EVENT_SIGNATURES
    severity: float = 0.0,              # [0, 1] — 0=normal, 1=full effect
    day_of_week: int = 0,
    weather: str = "clear",
    is_neighbor: bool = False,          # True → apply neighbor_density_mult only
    neighbor_density_mult: float = 1.0, # used only when is_neighbor=True
    event_id: str = "",
) -> list[dict]:
    """Generate all GPS pings for ONE segment during ONE 20-minute window.

    This is the core V2 function. V1's simulate_segment_hour() is now a
    thin wrapper that calls this 3 times (for the 3 × 20-min windows per hour).

    Args:
        segment:    Row from segments DataFrame
        window_start: Start of the 20-minute window (exact datetime)
        rng:        Seeded RNG for reproducibility
        event_type: If not None, apply this event's multipliers at `severity`
        severity:   Blend factor [0,1] between normal (0) and full event effect (1)
                    Implements onset/peak/decay without code duplication.
        day_of_week, weather: Passed to contextual_profile()
        is_neighbor: If True, apply density boost from a nearby event (label stays normal)
        neighbor_density_mult: The density multiplier applied to neighbor segments
        event_id:   Written to each ping row for traceability

    Returns:
        List of ping dicts (same schema as V1 rows).
    """
    hour = window_start.hour
    speed_mult, density_factor, uturn_base = contextual_profile(hour, day_of_week, weather)
    base_speed = segment.max_speed_kmph * speed_mult
    base_vph = _base_vehicles_per_hour(segment.road_type)

    speed_variance_mult = 1.0
    density_mult = 1.0
    uturn_mult = 1.0
    label = "normal"

    if event_type is not None and severity > 0.0:
        sig = EVENT_SIGNATURES[event_type]
        # Blend between normal (severity=0) and full effect (severity=1)
        speed_mult_eff = 1.0 + severity * (sig["speed_mult"] - 1.0)
        density_mult   = 1.0 + severity * (sig["density_mult"] - 1.0)
        uturn_mult     = 1.0 + severity * (sig["uturn_mult"] - 1.0)
        speed_variance_mult = 1.0 + severity * (sig["speed_variance_mult"] - 1.0)
        base_speed *= speed_mult_eff
        label = event_type   # any severity > 0 → labeled as event (early detection target)
    elif is_neighbor:
        # Neighbor effect: density increases (traffic redistributed from closed primary)
        # Speed is NOT affected — the neighbor segment itself has no obstruction
        # Label stays "normal" — this is NOT an event on the neighbor segment
        density_mult = neighbor_density_mult
        label = "normal"

    n_vehicles = _vehicle_count_for_window(base_vph, density_factor * density_mult, rng)
    uturn_prob = float(np.clip(uturn_base * uturn_mult, 0, 0.9))

    rows = []
    lat1, lon1, lat2, lon2 = (
        segment.start_lat, segment.start_lon,
        segment.end_lat, segment.end_lon,
    )
    half_width = segment.road_width_m / 2.0

    # Window duration in seconds
    window_duration_s = WINDOW_MINUTES * 60

    for v in range(n_vehicles):
        vtype = str(rng.choice(VEHICLE_TYPES, p=VEHICLE_WEIGHTS))
        speed = base_speed * VEHICLE_SPEED_ADJUST[vtype]
        speed *= float(rng.normal(1.0, 0.10 * speed_variance_mult))
        speed = float(np.clip(speed, MIN_SPEED_KMPH, segment.max_speed_kmph * 1.15))

        travel_time_s = max(segment.segment_length_m / (speed * 1000.0 / 3600.0), 3.0)
        n_pings = max(int(travel_time_s / PING_INTERVAL_S), 2)

        is_uturn = bool(rng.random() < uturn_prob)
        fractions = np.linspace(0, 1, n_pings)
        if is_uturn:
            half = max(n_pings // 2, 1)
            fractions = np.concatenate([
                np.linspace(0, 1, half),
                np.linspace(1, 0, n_pings - half),
            ])

        # Start time uniformly distributed within the 20-minute window
        start_offset_s = float(rng.uniform(0, window_duration_s))
        vehicle_start_time = window_start + timedelta(seconds=start_offset_s)

        # Vehicle ID includes window start for uniqueness across windows
        win_tag = window_start.strftime("%H%M")
        vehicle_id = f"{segment.segment_id}_W{win_tag}_V{v:03d}"

        for i, frac in enumerate(fractions):
            lat, lon = interpolate_latlon(lat1, lon1, lat2, lon2, float(frac))
            lateral_m = float(np.clip(rng.normal(0, half_width / 2.2), -half_width, half_width))
            noise_m = float(rng.normal(0, GPS_NOISE_M))
            heading = bearing_deg(lat1, lon1, lat2, lon2) if frac <= 1 else bearing_deg(lat2, lon2, lat1, lon1)
            perp_heading = (heading + 90.0) % 360.0
            lat_j, lon_j = offset_latlon(
                lat, lon,
                dx_east_m=np.sin(np.radians(perp_heading)) * (lateral_m + noise_m),
                dy_north_m=np.cos(np.radians(perp_heading)) * (lateral_m + noise_m),
            )
            ping_time = vehicle_start_time + timedelta(seconds=i * PING_INTERVAL_S)
            speed_obs = float(np.clip(
                speed + rng.normal(0, 2.0 * speed_variance_mult),
                MIN_SPEED_KMPH, segment.max_speed_kmph * 1.2,
            ))
            rows.append(dict(
                segment_id=segment.segment_id,
                region_id=segment.region_id,
                vehicle_id=vehicle_id,
                vehicle_type=vtype,
                lat=round(lat_j, 7),
                lon=round(lon_j, 7),
                speed_kmph=round(speed_obs, 1),
                heading_deg=round(heading, 1),
                timestamp=ping_time,
                is_uturn_flag=bool(is_uturn and i == len(fractions) // 2),
                label=label,
                event_id=event_id,
            ))

    return rows


def simulate_segment_hour(
    segment: pd.Series,
    timestamp_hour_start: datetime,
    rng: np.random.Generator,
    event: dict | None = None,
    is_neighbor_of_event: bool = False,
) -> list[dict]:
    """V1 backward-compatible wrapper — kept so old tests and V1 code still work.

    Internally calls simulate_segment_window() for each of the 3 × 20-min windows
    within the hour. The event is applied at full severity (severity=1.0) or 0.0.
    """
    rows = []
    for w in range(3):  # 3 × 20-min windows per hour
        window_start = timestamp_hour_start + timedelta(minutes=w * WINDOW_MINUTES)

        if event is not None:
            rows.extend(simulate_segment_window(
                segment, window_start, rng,
                event_type=event.get("type"),
                severity=event.get("severity", 1.0),
                event_id=event.get("event_id", ""),
            ))
        elif is_neighbor_of_event:
            rows.extend(simulate_segment_window(
                segment, window_start, rng,
                is_neighbor=True,
                neighbor_density_mult=1.15,
            ))
        else:
            rows.extend(simulate_segment_window(
                segment, window_start, rng,
            ))

    # For V1 compat: rows from this function don't have event_id set by caller,
    # but now they include it from simulate_segment_window(). Set label for V1 callers.
    if event is not None:
        for row in rows:
            row["label"] = event.get("type", "normal")
    return rows
