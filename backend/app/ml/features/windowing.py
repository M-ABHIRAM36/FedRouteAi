"""
Sliding-Window Feature Extraction
------------------------------------
Pure functions that turn raw GPS ping groups into feature vectors for ML training.

These functions implement the SAME ratio logic as:
    services/event_detection/signature_extractor.py::extract_signature()

...but operate on pandas DataFrames (for batch training) instead of ORM
objects (for live detection). This keeps the logic consistent without
creating a circular import between the ML package and the live service.

The model NEVER sees raw GPS values (lat, lon, speed, heading).
It only sees ratios relative to that segment's historical baseline.

Feature vector layout (N_FEATURES = 10):
    0  speed_ratio         cur_avg_speed / baseline_avg_speed
    1  density_ratio       cur_vehicle_count / expected_vehicles_in_window
    2  uturn_ratio         cur_uturn_rate / baseline_uturn_rate
    3  variance_ratio      cur_speed_std / baseline_speed_std
    4  hour_of_day         timestamp.hour / 24  (normalized)
    5  road_type           ordinal: residential=0, collector=1, arterial=2, highway_link=3
    6  lane_count          Segment.number_of_lanes (raw int, 1-4 in dataset)
    7  flood_prone         0 or 1
    8  neighbor_avg_speed  mean speed_ratio of 1-hop neighbors in same window (0 if unavailable)
    9  neighbor_density    mean density_ratio of 1-hop neighbors in same window (0 if unavailable)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

# Feature vector size — used by config and model definitions
N_FEATURES = 10

WINDOW_MINUTES = 20  # matches SIGNATURE_WINDOW_MINUTES in orchestrator.py

# Ordinal encoding: road_type string → int (order reflects capacity / speed limit)
ROAD_TYPE_ORDINAL: dict[str, int] = {
    "residential": 0,
    "collector": 1,
    "arterial": 2,
    "highway_link": 3,
}

# Small floors applied identically to signature_extractor.py to avoid divide-by-zero
_BASELINE_SPEED_FLOOR = 1.0
_BASELINE_DENSITY_FLOOR = 0.5
_BASELINE_UTURN_FLOOR = 0.01
_BASELINE_STD_FLOOR = 0.5


def _compute_ratios(
    group: pd.DataFrame,
    baseline_speed: float,
    baseline_density_for_window: float,
    baseline_uturn: float,
    baseline_std: float,
) -> tuple[float, float, float, float]:
    """Compute the four ratio features for one (segment, window) group of pings.
    Mirrors the math in signature_extractor.py::extract_signature()."""
    speeds = group["speed_kmph"].values
    vehicle_count = group["vehicle_id"].nunique()
    uturn_count = group["is_uturn_flag"].sum()

    cur_avg_speed = float(speeds.mean()) if len(speeds) > 0 else baseline_speed
    cur_variance = float(speeds.var(ddof=1)) if len(speeds) > 1 else 0.0
    cur_std = float(np.sqrt(cur_variance))
    cur_uturn_rate = float(uturn_count / len(group)) if len(group) > 0 else 0.0

    speed_ratio = round(cur_avg_speed / max(baseline_speed, _BASELINE_SPEED_FLOOR), 3)
    density_ratio = round(vehicle_count / max(baseline_density_for_window, _BASELINE_DENSITY_FLOOR), 3)
    uturn_ratio = round(cur_uturn_rate / max(baseline_uturn, _BASELINE_UTURN_FLOOR), 3)
    variance_ratio = round(cur_std / max(baseline_std, _BASELINE_STD_FLOOR), 3)

    return speed_ratio, density_ratio, uturn_ratio, variance_ratio


def extract_windowed_features(
    gps_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    memory_df: pd.DataFrame,
) -> pd.DataFrame:
    """Main entry point.  Turns raw DataFrames into a labeled feature table.

    Args:
        gps_df:      GPS pings with columns: segment_id, region_id, vehicle_id,
                     speed_kmph, timestamp (datetime), is_uturn_flag, label
        segments_df: Segment metadata with: segment_id, region_id, road_type,
                     number_of_lanes, flood_prone, neighbor_segments
        memory_df:   Per-segment-per-hour baselines. Supports two formats:
                     V1: segment_id, hour_of_day, avg_speed_kmph, std_speed_kmph,
                         avg_vehicle_count, uturn_rate
                     V2: adds day_type ('weekday'|'weekend') and
                         avg_vehicle_count_per_20min (already per-window, not per-hour)
                     The correct format is auto-detected from the columns present.

    Returns:
        DataFrame with columns:
            segment_id, region_id, window_start, label,
            [10 feature columns], [raw ratio pair for neighbor lookup]
        One row per (segment_id, 20-min tumbling window) that has a valid baseline.

    Dropped:
        - Windows where no baseline exists for that segment + hour (+ day_type in V2)
        - Rows with *_neighbor_effect labels (V1 datasets only; V2 never generates them)
        - Windows with 0 pings (shouldn't happen, but defensive)
    """
    # ---- Ensure timestamp is datetime ----
    if not pd.api.types.is_datetime64_any_dtype(gps_df["timestamp"]):
        gps_df = gps_df.copy()
        gps_df["timestamp"] = pd.to_datetime(gps_df["timestamp"])

    # ---- Build segment lookup dicts (O(1) field access during windowing) ----
    seg_meta: dict[str, dict] = (
        segments_df.set_index("segment_id")[
            ["region_id", "road_type", "number_of_lanes", "flood_prone", "neighbor_segments"]
        ].to_dict("index")
    )

    # ---- Auto-detect memory format (V1 vs V2) and build baseline lookup ----
    memory_df = memory_df.copy()
    _is_v2_memory = "day_type" in memory_df.columns and "avg_vehicle_count_per_20min" in memory_df.columns
    _density_col = "avg_vehicle_count_per_20min" if _is_v2_memory else "avg_vehicle_count"

    if _is_v2_memory:
        # V2: key is (segment_id, hour_of_day, day_type)
        memory_df["_key"] = list(zip(
            memory_df["segment_id"],
            memory_df["hour_of_day"],
            memory_df["day_type"],
        ))
    else:
        # V1: key is (segment_id, hour_of_day)
        memory_df["_key"] = list(zip(memory_df["segment_id"], memory_df["hour_of_day"]))

    baseline_lookup: dict = {row["_key"]: row.to_dict() for _, row in memory_df.iterrows()}

    # ---- Drop neighbor_effect labels (V1 datasets only; V2 never generates them) ----
    gps_df = gps_df[~gps_df["label"].str.endswith("_neighbor_effect", na=False)].copy()

    # ---- Add tumbling window key (floor timestamp to 20-min bucket) ----
    gps_df["window_start"] = gps_df["timestamp"].dt.floor(f"{WINDOW_MINUTES}min")
    gps_df["hour_of_day"] = gps_df["timestamp"].dt.hour
    if _is_v2_memory:
        gps_df["day_of_week"] = gps_df["timestamp"].dt.dayofweek
        gps_df["day_type"] = gps_df["day_of_week"].apply(
            lambda d: "weekday" if d < 5 else "weekend"
        )

    # ---- Group by (segment_id, window_start) ----
    records = []
    groups = gps_df.groupby(["segment_id", "window_start"], sort=False)

    for (segment_id, window_start), group in groups:
        if len(group) == 0:
            continue

        meta = seg_meta.get(segment_id)
        if meta is None:
            continue  # segment not in segments.csv (shouldn't happen)

        hour = int(group["hour_of_day"].iloc[0])
        if _is_v2_memory:
            day_type = group["day_type"].iloc[0] if "day_type" in group.columns else "weekday"
            baseline = baseline_lookup.get((segment_id, hour, day_type))
            # Fallback: if exact (seg, hour, day_type) is missing, try (seg, hour, weekday)
            if baseline is None:
                baseline = baseline_lookup.get((segment_id, hour, "weekday"))
        else:
            baseline = baseline_lookup.get((segment_id, hour))
        if baseline is None:
            continue  # no historical baseline for this hour → can't compute ratios

        # V2: density is already per-20-min. V1: scale hourly count to window.
        if _is_v2_memory:
            baseline_density_for_window = float(baseline.get(_density_col, 1.0))
        else:
            baseline_density_for_window = baseline["avg_vehicle_count"] * (WINDOW_MINUTES / 60.0)

        speed_ratio, density_ratio, uturn_ratio, variance_ratio = _compute_ratios(
            group,
            baseline_speed=baseline["avg_speed_kmph"],
            baseline_density_for_window=baseline_density_for_window,
            baseline_uturn=baseline["uturn_rate"],
            baseline_std=baseline["std_speed_kmph"],
        )

        # Road type: ordinal encode, default to 0 if unknown string
        road_type_enc = ROAD_TYPE_ORDINAL.get(str(meta["road_type"]).lower(), 0)
        lane_count = int(meta["number_of_lanes"])
        flood_prone = int(bool(meta["flood_prone"]))

        # Hour normalized
        hour_norm = round(hour / 24.0, 4)

        # Label: majority label in this window (should be uniform per window in synthetic data)
        label = group["label"].mode()[0] if not group["label"].isna().all() else "normal"

        records.append({
            "segment_id": segment_id,
            "region_id": str(meta["region_id"]),
            "window_start": window_start,
            "hour_of_day": hour,
            "label": label,
            # Feature vector (features 0-7; 8-9 filled in a second pass)
            "speed_ratio": speed_ratio,
            "density_ratio": density_ratio,
            "uturn_ratio": uturn_ratio,
            "variance_ratio": variance_ratio,
            "hour_of_day_norm": hour_norm,
            "road_type": road_type_enc,
            "lane_count": lane_count,
            "flood_prone": flood_prone,
            "neighbor_avg_speed": 0.0,   # filled below
            "neighbor_density": 0.0,     # filled below
            # Raw for neighbor lookup
            "_neighbor_segments": str(meta["neighbor_segments"] or ""),
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # ---- Fill neighbor features (features 8-9) ----
    # Build a speed/density lookup indexed by (segment_id, window_start)
    ratio_lookup: dict[tuple, tuple[float, float]] = {
        (row["segment_id"], row["window_start"]): (row["speed_ratio"], row["density_ratio"])
        for _, row in df.iterrows()
    }

    neighbor_avg_speeds = []
    neighbor_densities = []
    for _, row in df.iterrows():
        neighbor_ids = [s for s in row["_neighbor_segments"].split(";") if s]
        ws = row["window_start"]
        ratios = [ratio_lookup.get((n, ws)) for n in neighbor_ids if (n, ws) in ratio_lookup]
        if ratios:
            neighbor_avg_speeds.append(round(float(np.mean([r[0] for r in ratios])), 3))
            neighbor_densities.append(round(float(np.mean([r[1] for r in ratios])), 3))
        else:
            neighbor_avg_speeds.append(0.0)
            neighbor_densities.append(0.0)

    df["neighbor_avg_speed"] = neighbor_avg_speeds
    df["neighbor_density"] = neighbor_densities
    df = df.drop(columns=["_neighbor_segments"])

    return df


# Canonical feature column order — used by pipeline and model inference
FEATURE_COLUMNS: list[str] = [
    "speed_ratio",
    "density_ratio",
    "uturn_ratio",
    "variance_ratio",
    "hour_of_day_norm",
    "road_type",
    "lane_count",
    "flood_prone",
    "neighbor_avg_speed",
    "neighbor_density",
]
