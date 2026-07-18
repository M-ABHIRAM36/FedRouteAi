"""
generate_dataset.py  (V2)
--------------------------
Orchestrates the full FedRouteAI synthetic dataset build, V2.

V2 vs V1 — seven changes:
  1. Two-phase simulation:
       Memory phase (days 1-10): normal traffic only → builds stable historical baselines.
       Event phase  (days 11-14): events injected → this is the training CSV.
     The two phases use separate calendar days so event-contaminated pings
     cannot pollute the historical memory.

  2. 20-minute simulation granularity (matching the ML window size).
     V1 simulated at 1-hour granularity, which was coarser than the 20-min
     feature window, producing exactly 1 window per short event (accidents).

  3. Event lifecycle: each event goes through onset → peak → decay at
     20-min resolution. The severity function blends between normal (0.0)
     and full effect (1.0) per window, producing transitional training examples.

  4. Contextual event placement:
       - Hour eligibility: events only start during traffic hours (no 3 AM events)
       - Road type affinity: each event type has preferred road types (prevents
         the XGBoost leakage where construction always landed on residential roads)

  5. Neighbor effect re-labeled "normal":
     V1 labeled neighbor pings as "{event_type}_neighbor_effect", which created
     15 label classes and forced the feature pipeline to drop 42k pings.
     V2 labels neighbor pings as "normal" but simulates their density increase
     correctly. Graph reasoning (not the ML classifier) handles neighbor effects.

  6. Richer historical memory: keys on (segment, hour, day_type) where
     day_type ∈ {weekday, weekend}. Stores avg_vehicle_count_per_20min (not
     per-hour). Baseline built from 10 memory days → stable, ≥20 samples/cell.

  7. Diagnostics: writes diagnostics/ CSVs automatically so you can verify
     the dataset without running a separate analysis script.

Output: data/raw/fedrouteai_dataset_v2/   (V1 is NOT overwritten)
Same CSV schema as V1 — pipeline.py, windowing.py, and the backend are unchanged.
"""
from __future__ import annotations

import os
import math
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd

from road_network import build_road_network
from traffic_sim import simulate_segment_window, WINDOW_MINUTES
from event_signatures import EVENT_SIGNATURES, EVENT_TYPES, HOUR_BUCKETS

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class V2Config:
    seed: int = 42
    sim_start: datetime = field(default_factory=lambda: datetime(2026, 7, 7, 0, 0, 0))  # Monday

    # Timeline
    memory_days: int = 10     # days 1-10: normal only → baseline
    event_days: int = 4       # days 11-14: events → training data

    # Event density: default for direct runs; calibration script overrides at runtime via V2Config
    # Calibration recommends High=(28,35) to hit Macro F1 > 0.55 and rare-class F1 > 0.30
    events_per_region_per_day_min: int = 28
    events_per_region_per_day_max: int = 35

    # Event type sampling weights (must sum to 1.0)
    event_type_weights: dict = field(default_factory=lambda: {
        "congestion":   0.30,
        "road_damage":  0.25,
        "accident":     0.20,
        "construction": 0.10,
        "flood":        0.05,
        "road_block":   0.05,
        "diversion":    0.05,
    })

    # Onset/decay label threshold: label as event type at any severity > this value
    # 0.0 means ALL onset/decay windows are labeled as the event (early detection)
    min_severity_for_label: float = 0.0

    # Memory
    memory_day_type_granularity: Literal["weekday_weekend", "all_7"] = "weekday_weekend"
    min_samples_per_memory_cell: int = 20

    # Output
    out_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "raw", "fedrouteai_dataset_v2"
    ))

    # Weather schedule: one per simulated day (memory + event days)
    # Derived at runtime — not a config field
    @property
    def total_days(self) -> int:
        return self.memory_days + self.event_days


# ──────────────────────────────────────────────────────────────────────────────
# Weather schedule
# ──────────────────────────────────────────────────────────────────────────────

def build_weather_schedule(total_days: int, rng: np.random.Generator) -> list[str]:
    """Returns a weather state for each simulated day.
    Clear dominates (80%), rain is occasional (15%), heavy_rain rare (5%).
    """
    states = rng.choice(
        ["clear", "rain", "heavy_rain"],
        size=total_days,
        p=[0.80, 0.15, 0.05],
    )
    return [str(s) for s in states]


# ──────────────────────────────────────────────────────────────────────────────
# Event lifecycle helpers
# ──────────────────────────────────────────────────────────────────────────────

def severity_at_window(
    window_idx: int,       # 0 = first window of the event
    onset_windows: int,
    peak_windows: int,
    decay_windows: int,
    peak_severity: float,
) -> float:
    """Return severity [0, 1] for a specific 20-min window within the event lifecycle."""
    if window_idx < onset_windows:
        # Linear rise from 0 to peak_severity
        progress = (window_idx + 1) / max(onset_windows, 1)
        return peak_severity * progress
    elif window_idx < onset_windows + peak_windows:
        return peak_severity
    else:
        remaining = window_idx - onset_windows - peak_windows
        decay_fraction = remaining / max(decay_windows, 1)
        return max(0.0, peak_severity * (1.0 - decay_fraction))


def _minutes_to_windows(minutes: int) -> int:
    """Convert minutes to number of 20-min windows (ceiling)."""
    return math.ceil(minutes / WINDOW_MINUTES)


# ──────────────────────────────────────────────────────────────────────────────
# Eligible start hours
# ──────────────────────────────────────────────────────────────────────────────

def _build_hour_eligibility(preferred_buckets: list[str]) -> tuple[list[int], list[float]]:
    """Return (hours, weights) for sampling the start hour of an event.

    preferred_buckets: the event type's preferred_hours list from event_signatures.py.
    If empty or None, uses all non-night buckets with uniform weight.
    """
    hour_weight: dict[int, float] = {}
    for bucket_name, (h_start, h_end, base_weight) in HOUR_BUCKETS.items():
        if base_weight == 0.0:
            continue  # night: never eligible
        # Determine multiplier for preferred buckets
        multiplier = 2.0 if bucket_name in (preferred_buckets or []) else 1.0
        effective_weight = base_weight * multiplier
        # Assign to all hours in the bucket (handle wrap-around at midnight)
        if h_start <= h_end:
            hour_range = range(h_start, h_end + 1)
        else:
            hour_range = list(range(h_start, 24)) + list(range(0, h_end + 1))
        for h in hour_range:
            hour_weight[h] = hour_weight.get(h, 0.0) + effective_weight

    if not hour_weight:
        # Fallback: all daytime hours equally
        hour_weight = {h: 1.0 for h in range(6, 23)}

    hours = sorted(hour_weight.keys())
    weights = [hour_weight[h] for h in hours]
    total = sum(weights)
    weights = [w / total for w in weights]
    return hours, weights


# ──────────────────────────────────────────────────────────────────────────────
# Segment selection (road type affinity)
# ──────────────────────────────────────────────────────────────────────────────

def _select_segment(
    event_type: str,
    region_segments: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.Series | None:
    """Select a segment for the given event type using road_type_weights affinity."""
    sig = EVENT_SIGNATURES[event_type]
    road_type_weights = sig.get("road_type_weights")

    if road_type_weights is None:
        # flood: use flood_prone flag
        pool = region_segments[region_segments["flood_prone"]]
        if len(pool) == 0:
            return None
        idx = rng.integers(0, len(pool))
        return pool.iloc[idx]

    # Compute per-segment sampling weight from its road_type
    weights = region_segments["road_type"].map(road_type_weights).fillna(0.0).values
    if weights.sum() == 0:
        return None
    weights = weights / weights.sum()
    idx = rng.choice(len(region_segments), p=weights)
    return region_segments.iloc[idx]


# ──────────────────────────────────────────────────────────────────────────────
# Event planning (V2)
# ──────────────────────────────────────────────────────────────────────────────

def plan_events_v2(
    segments: pd.DataFrame,
    config: V2Config,
    event_day_indices: list[int],   # day indices within the total sim (0-based)
    rng: np.random.Generator,
) -> list[dict]:
    """Plan all events for the event phase.

    Returns a list of event dicts, each containing:
      event_id, event_type, region_id, primary_segment_id,
      start_time, peak_severity, peak_duration_min,
      onset_windows, peak_windows, decay_windows,
      window_schedule: list of (window_start_datetime, severity) tuples,
      affected_neighbors: list of neighbor segment_ids
    """
    events = []
    seg_by_region = dict(list(segments.groupby("region_id")))
    event_id_counter = 1

    # Pre-compute event type weights array for sampling
    et_types = list(config.event_type_weights.keys())
    et_weights = np.array([config.event_type_weights[t] for t in et_types], dtype=float)
    et_weights /= et_weights.sum()

    # Track which (segment_id, window_start) pairs are already taken
    occupied: set[tuple[str, datetime]] = set()

    for day_idx in event_day_indices:
        day_start = config.sim_start + timedelta(days=day_idx)
        day_of_week = day_start.weekday()

        for region_id, region_segs in seg_by_region.items():
            n_events = int(rng.integers(
                config.events_per_region_per_day_min,
                config.events_per_region_per_day_max + 1,
            ))

            for _ in range(n_events):
                # 1. Choose event type
                event_type = str(et_types[rng.choice(len(et_types), p=et_weights)])
                sig = EVENT_SIGNATURES[event_type]

                # 2. Choose start hour using eligibility weights
                preferred = sig.get("preferred_hours") or []
                eligible_hours, hour_weights = _build_hour_eligibility(preferred)
                start_hour = int(rng.choice(eligible_hours, p=hour_weights))

                # 3. Choose duration (total including onset + decay)
                dur_min_lo, dur_min_hi = sig["duration_min_range"]
                total_duration_min = int(rng.integers(dur_min_lo, dur_min_hi + 1))
                onset_min = sig["onset_min"]
                decay_min = sig["decay_min"]
                peak_min = max(WINDOW_MINUTES, total_duration_min - onset_min - decay_min)

                onset_w = _minutes_to_windows(onset_min)
                peak_w = _minutes_to_windows(peak_min)
                decay_w = _minutes_to_windows(decay_min)
                total_windows = onset_w + peak_w + decay_w

                # 4. Choose segment (road type affinity)
                primary = _select_segment(event_type, region_segs, rng)
                if primary is None:
                    continue

                # 5. Check for window conflicts — TRUNCATE at first conflict
                # (don't skip the whole event; two events on the same segment at
                # different hours is physically realistic: morning accident +
                # afternoon construction on the same busy arterial)
                event_window_starts = []
                for w_idx in range(total_windows):
                    window_dt = (
                        day_start
                        + timedelta(hours=start_hour)
                        + timedelta(minutes=w_idx * WINDOW_MINUTES)
                    )
                    if window_dt.day != day_start.day:
                        break  # past midnight — truncate
                    key = (primary.segment_id, window_dt)
                    if key in occupied:
                        break  # truncate here; keep windows collected so far
                    event_window_starts.append(window_dt)

                # Need at least 1 window to be worth recording
                if not event_window_starts:
                    continue

                # Mark chosen windows as occupied
                for ws in event_window_starts:
                    occupied.add((primary.segment_id, ws))

                # 6. Compute per-window severity schedule
                peak_severity = float(rng.uniform(0.65, 1.0))
                window_schedule = []
                for w_idx, ws in enumerate(event_window_starts):
                    sev = severity_at_window(w_idx, onset_w, peak_w, decay_w, peak_severity)
                    window_schedule.append((ws, sev))

                # 7. Neighbor segments
                neighbor_ids = [
                    s for s in str(primary.get("neighbor_segments", "")).split(";") if s
                ]

                start_time = day_start + timedelta(hours=start_hour)
                end_time = event_window_starts[-1] + timedelta(minutes=WINDOW_MINUTES)

                events.append(dict(
                    event_id=f"EVT_{event_id_counter:04d}",
                    event_type=event_type,
                    region_id=region_id,
                    primary_segment_id=primary.segment_id,
                    start_time=start_time,
                    end_time=end_time,
                    duration_hours=round((end_time - start_time).total_seconds() / 3600, 2),
                    severity=round(peak_severity, 2),
                    affected_neighbors=";".join(neighbor_ids),
                    # V2 internals (not written to event_log.csv)
                    _window_schedule=window_schedule,
                    _onset_windows=onset_w,
                    _peak_windows=peak_w,
                    _decay_windows=decay_w,
                    _day_of_week=day_of_week,
                ))
                event_id_counter += 1

    print(f"     Planned {len(events)} events across {len(event_day_indices)} event days")
    return events


# ──────────────────────────────────────────────────────────────────────────────
# Memory phase simulation (days 1 - memory_days)
# ──────────────────────────────────────────────────────────────────────────────

def memory_phase(
    segments: pd.DataFrame,
    config: V2Config,
    weather_schedule: list[str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Simulate memory_days of NORMAL traffic. Returns a pings DataFrame
    (not written to training CSV — only used for building historical memory).
    """
    all_rows = []
    windows_per_day = (24 * 60) // WINDOW_MINUTES  # 72 windows per day

    for day_idx in range(config.memory_days):
        day_start = config.sim_start + timedelta(days=day_idx)
        day_of_week = day_start.weekday()
        weather = weather_schedule[day_idx]

        day_rows = []
        for _, seg in segments.iterrows():
            for w_idx in range(windows_per_day):
                window_start = day_start + timedelta(minutes=w_idx * WINDOW_MINUTES)
                rows = simulate_segment_window(
                    seg, window_start, rng,
                    day_of_week=day_of_week,
                    weather=weather,
                )
                for row in rows:
                    row["day_of_week"] = day_of_week
                day_rows.extend(rows)

        all_rows.extend(day_rows)
        print(f"     Memory day {day_idx + 1}/{config.memory_days}: {len(day_rows):,} pings "
              f"(weather={weather}, day={day_start.strftime('%a')})")

    print(f"     Memory phase total: {len(all_rows):,} normal pings")
    return pd.DataFrame(all_rows)


# ──────────────────────────────────────────────────────────────────────────────
# Event phase simulation (days memory_days+1 to total_days)
# ──────────────────────────────────────────────────────────────────────────────

def event_phase(
    segments: pd.DataFrame,
    events: list[dict],
    config: V2Config,
    weather_schedule: list[str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Simulate event_days of traffic WITH events. This is the training data.

    Returns pings DataFrame written to gps_pings_all.csv.
    Neighbor pings are labeled 'normal' — NOT _neighbor_effect.
    """
    windows_per_day = (24 * 60) // WINDOW_MINUTES

    # Build fast lookups:
    # primary_lookup[(segment_id, window_start)] = (event_type, severity, event_id, day_of_week)
    # neighbor_lookup[(segment_id, window_start)] = neighbor_density_mult
    primary_lookup: dict[tuple, dict] = {}
    neighbor_lookup: dict[tuple, float] = {}

    for ev in events:
        sig = EVENT_SIGNATURES[ev["event_type"]]
        neighbor_dm = sig["neighbor_density_mult"]
        for (ws, sev) in ev["_window_schedule"]:
            key = (ev["primary_segment_id"], ws)
            primary_lookup[key] = {
                "event_type": ev["event_type"],
                "severity": sev,
                "event_id": ev["event_id"],
                "day_of_week": ev["_day_of_week"],
            }
            for n_id in ev["affected_neighbors"].split(";"):
                if n_id:
                    n_key = (n_id, ws)
                    # Use max density mult if multiple events affect the same neighbor
                    neighbor_lookup[n_key] = max(
                        neighbor_lookup.get(n_key, 1.0), neighbor_dm
                    )

    event_day_start_idx = config.memory_days
    all_rows = []

    for day_offset in range(config.event_days):
        day_idx = event_day_start_idx + day_offset
        day_start = config.sim_start + timedelta(days=day_idx)
        day_of_week = day_start.weekday()
        weather = weather_schedule[day_idx]

        for _, seg in segments.iterrows():
            for w_idx in range(windows_per_day):
                window_start = day_start + timedelta(minutes=w_idx * WINDOW_MINUTES)
                p_key = (seg.segment_id, window_start)
                n_key = (seg.segment_id, window_start)

                if p_key in primary_lookup:
                    ev_info = primary_lookup[p_key]
                    rows = simulate_segment_window(
                        seg, window_start, rng,
                        event_type=ev_info["event_type"],
                        severity=ev_info["severity"],
                        day_of_week=ev_info["day_of_week"],
                        weather=weather,
                        event_id=ev_info["event_id"],
                    )
                elif n_key in neighbor_lookup:
                    # Neighbor: normal label, elevated density
                    rows = simulate_segment_window(
                        seg, window_start, rng,
                        is_neighbor=True,
                        neighbor_density_mult=neighbor_lookup[n_key],
                        day_of_week=day_of_week,
                        weather=weather,
                    )
                else:
                    rows = simulate_segment_window(
                        seg, window_start, rng,
                        day_of_week=day_of_week,
                        weather=weather,
                    )

                all_rows.extend(rows)

    print(f"     Event phase: {len(all_rows):,} pings across {config.event_days} days")
    return pd.DataFrame(all_rows)


# ──────────────────────────────────────────────────────────────────────────────
# Historical memory (V2)
# ──────────────────────────────────────────────────────────────────────────────

def build_historical_memory_v2(
    memory_pings: pd.DataFrame,
    config: V2Config,
) -> pd.DataFrame:
    """Build per-segment-hour-day_type baseline from the memory phase pings only.

    day_type: 'weekday' if day_of_week < 5, else 'weekend'.
    avg_vehicle_count_per_20min: true per-window vehicle count (not divided from hourly).
    """
    df = memory_pings[memory_pings["label"] == "normal"].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["window_start"] = df["timestamp"].dt.floor(f"{WINDOW_MINUTES}min")

    # Day type: weekday vs weekend
    df["day_type"] = df["day_of_week"].apply(lambda d: "weekday" if d < 5 else "weekend")

    # Count unique vehicles per (segment, window_start) for density baseline
    vehicle_counts = (
        df.groupby(["segment_id", "window_start", "hour_of_day", "day_type"])
        ["vehicle_id"].nunique()
        .reset_index()
        .rename(columns={"vehicle_id": "vehicles_this_window"})
    )

    # Speed and uturn stats per (segment, window_start, hour, day_type)
    speed_stats = (
        df.groupby(["segment_id", "window_start", "hour_of_day", "day_type"])
        .agg(
            avg_speed_kmph=("speed_kmph", "mean"),
            std_speed_kmph=("speed_kmph", "std"),
            uturn_rate=("is_uturn_flag", "mean"),
            sample_size=("speed_kmph", "count"),
        )
        .reset_index()
    )

    window_df = speed_stats.merge(vehicle_counts, on=["segment_id", "window_start", "hour_of_day", "day_type"])

    # Aggregate across all windows → per (segment, hour, day_type) baseline
    grouped = (
        window_df.groupby(["segment_id", "hour_of_day", "day_type"])
        .agg(
            avg_speed_kmph=("avg_speed_kmph", "mean"),
            std_speed_kmph=("std_speed_kmph", "mean"),
            avg_vehicle_count_per_20min=("vehicles_this_window", "mean"),
            uturn_rate=("uturn_rate", "mean"),
            sample_size=("sample_size", "sum"),
        )
        .reset_index()
    )
    grouped["avg_speed_kmph"] = grouped["avg_speed_kmph"].round(1)
    grouped["std_speed_kmph"] = grouped["std_speed_kmph"].fillna(0).round(2)
    grouped["avg_vehicle_count_per_20min"] = grouped["avg_vehicle_count_per_20min"].round(2)
    grouped["uturn_rate"] = grouped["uturn_rate"].round(3)

    # Apply global fallback for thin cells (< min threshold)
    global_avg_speed = grouped["avg_speed_kmph"].mean()
    global_std_speed = grouped["std_speed_kmph"].mean()
    thin_mask = grouped["sample_size"] < config.min_samples_per_memory_cell
    if thin_mask.sum() > 0:
        grouped.loc[thin_mask, "avg_speed_kmph"] = global_avg_speed
        grouped.loc[thin_mask, "std_speed_kmph"] = global_std_speed
        print(f"     Memory: {thin_mask.sum()} thin cells ({thin_mask.sum()/len(grouped)*100:.1f}%) filled with global fallback")

    return grouped


# ──────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ──────────────────────────────────────────────────────────────────────────────

def write_diagnostics(
    training_pings: pd.DataFrame,
    events: list[dict],
    memory: pd.DataFrame,
    out_dir: str,
) -> None:
    diag_dir = os.path.join(out_dir, "diagnostics")
    os.makedirs(diag_dir, exist_ok=True)

    # Label distribution
    dist = training_pings["label"].value_counts().reset_index()
    dist.columns = ["label", "ping_count"]
    dist["pct"] = (dist["ping_count"] / dist["ping_count"].sum() * 100).round(2)
    dist.to_csv(os.path.join(diag_dir, "label_distribution.csv"), index=False)

    # Window distribution (approximate: floor to 20-min windows)
    tp = training_pings.copy()
    tp["timestamp"] = pd.to_datetime(tp["timestamp"])
    tp["window_start"] = tp["timestamp"].dt.floor(f"{WINDOW_MINUTES}min")
    window_labels = (
        tp.groupby(["segment_id", "window_start"])["label"]
        .apply(lambda s: s.mode()[0])
        .reset_index()
    )
    wdist = window_labels["label"].value_counts().reset_index()
    wdist.columns = ["label", "window_count"]
    wdist["pct"] = (wdist["window_count"] / wdist["window_count"].sum() * 100).round(2)
    wdist.to_csv(os.path.join(diag_dir, "window_distribution.csv"), index=False)

    # Event density per region per day
    ev_df = pd.DataFrame([{k: v for k, v in e.items() if not k.startswith("_")} for e in events])
    if len(ev_df):
        ev_df["day"] = pd.to_datetime(ev_df["start_time"]).dt.date
        density = ev_df.groupby(["region_id", "day"])["event_id"].count().reset_index()
        density.columns = ["region_id", "day", "event_count"]
        density.to_csv(os.path.join(diag_dir, "event_density.csv"), index=False)

    # Memory stability
    memory["thin"] = memory["sample_size"] < 20
    stability = memory.groupby("day_type").agg(
        total_cells=("sample_size", "count"),
        thin_cells=("thin", "sum"),
        avg_samples=("sample_size", "mean"),
        min_samples=("sample_size", "min"),
    ).reset_index()
    stability.to_csv(os.path.join(diag_dir, "memory_stability.csv"), index=False)

    # Print summary
    print("\n" + "=" * 60)
    print("DATASET V2 — DIAGNOSTICS SUMMARY")
    print("=" * 60)
    total_windows = wdist["window_count"].sum()
    non_normal_windows = wdist.loc[wdist["label"] != "normal", "window_count"].sum()
    print(f"Total windows:       {total_windows:,}")
    print(f"Non-normal windows:  {non_normal_windows:,} ({non_normal_windows/total_windows*100:.1f}%)")
    print("\nWindow distribution:")
    for _, row in wdist.iterrows():
        print(f"  {row['label']:<20} {row['window_count']:>6,}  ({row['pct']:.1f}%)")
    print(f"\nTotal events:        {len(events)}")
    print(f"Memory cells:        {len(memory):,}")
    print(f"Thin memory cells:   {memory['thin'].sum()} ({memory['thin'].mean()*100:.1f}%)")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(config: V2Config | None = None):
    if config is None:
        config = V2Config()

    rng = np.random.default_rng(config.seed)

    if os.path.exists(config.out_dir):
        shutil.rmtree(config.out_dir)
    os.makedirs(config.out_dir)

    # ── Step 1: Build road network (unchanged from V1) ──────────────────
    print("1/7  Building road network...")
    segments, regions = build_road_network(seed=config.seed)
    print(f"     {len(segments)} segments across {len(regions)} regions")

    # ── Step 2: Build weather schedule ──────────────────────────────────
    print("2/7  Building weather schedule...")
    weather_schedule = build_weather_schedule(config.total_days, rng)
    rain_days = sum(1 for w in weather_schedule if w != "clear")
    print(f"     {config.total_days} days: {rain_days} rain/heavy-rain days, {config.total_days - rain_days} clear")

    # ── Step 3: Memory phase (days 1 - memory_days) ─────────────────────
    print(f"3/7  Memory phase: simulating {config.memory_days} days of normal traffic...")
    memory_pings = memory_phase(segments, config, weather_schedule, rng)

    # ── Step 4: Build historical memory from memory phase ───────────────
    print("4/7  Building historical memory (from memory phase only)...")
    memory = build_historical_memory_v2(memory_pings, config)
    print(f"     {len(memory):,} (segment, hour, day_type) baseline rows")

    # ── Step 5: Plan events for the event phase ──────────────────────────
    print("5/7  Planning events for event phase...")
    event_day_indices = list(range(config.memory_days, config.total_days))
    events = plan_events_v2(segments, config, event_day_indices, rng)
    if events:
        from collections import Counter
        type_counts = Counter(e["event_type"] for e in events)
        print(f"     Event types: {dict(sorted(type_counts.items()))}")

    # ── Step 6: Event phase (days memory_days+1 to total_days) ──────────
    print(f"6/7  Event phase: simulating {config.event_days} days with events...")
    training_pings = event_phase(segments, events, config, weather_schedule, rng)

    # ── Step 7: Write output ─────────────────────────────────────────────
    print("7/7  Writing output...")

    # Road network
    road_net_dir = os.path.join(config.out_dir, "road_network")
    os.makedirs(road_net_dir, exist_ok=True)
    segments.drop(columns=["node_start", "node_end"]).to_csv(
        os.path.join(road_net_dir, "segments.csv"), index=False)
    regions.to_csv(os.path.join(road_net_dir, "regions.csv"), index=False)

    # Global training data
    global_dir = os.path.join(config.out_dir, "global")
    os.makedirs(global_dir, exist_ok=True)
    training_pings.to_csv(os.path.join(global_dir, "gps_pings_all.csv"), index=False)
    memory.to_csv(os.path.join(global_dir, "segment_historical_memory.csv"), index=False)

    # Event log (drop internal _* keys)
    event_log = pd.DataFrame([
        {k: v for k, v in e.items() if not k.startswith("_")}
        for e in events
    ])
    if len(event_log):
        event_log.to_csv(os.path.join(global_dir, "event_log.csv"), index=False)

    # Federated splits
    federated_dir = os.path.join(config.out_dir, "federated")
    os.makedirs(federated_dir, exist_ok=True)
    for region_id, seg_group in segments.groupby("region_id"):
        region_dir = os.path.join(federated_dir, str(region_id))
        os.makedirs(region_dir, exist_ok=True)
        seg_ids = set(seg_group.segment_id)
        training_pings[training_pings.segment_id.isin(seg_ids)].to_csv(
            os.path.join(region_dir, "gps_pings.csv"), index=False)
        memory[memory.segment_id.isin(seg_ids)].to_csv(
            os.path.join(region_dir, "segment_historical_memory.csv"), index=False)
        seg_group.drop(columns=["node_start", "node_end"]).to_csv(
            os.path.join(region_dir, "segments.csv"), index=False)
        if len(event_log):
            event_log[event_log.region_id == region_id].to_csv(
                os.path.join(region_dir, "event_log.csv"), index=False)

    # Diagnostics
    write_diagnostics(training_pings, events, memory, config.out_dir)
    print(f"\nOutput: {config.out_dir}")
    return segments, regions, training_pings, memory, events


if __name__ == "__main__":
    main()
