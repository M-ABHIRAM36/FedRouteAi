"""Causal feature variants for aggregate Geo V2 traffic observations.

Feature construction intentionally has no target argument. Labels and scenario
truth are joined by the dataset builder only after this module returns.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from app.services.geo_v2.network import CanonicalNetwork
from app.ml.geo_v2.feature_contract import HISTORY_CADENCE_SECONDS


FORBIDDEN_TOKENS = (
    "label", "event", "scenario", "ground_truth", "vehicle_id", "device_id",
    "severity", "active_event", "target",
)
METADATA_COLUMNS = ["row_id", "split", "episode_id", "segment_id", "region_id", "timestamp"]

CURRENT_ONLY = [
    "avg_speed_kmph", "speed_std_kmph", "vehicle_count", "occupancy",
    "flow_rate_vph", "stopped_fraction", "hour_sin", "hour_cos",
    "road_type_code", "lane_count", "max_speed_kmph",
]
HISTORY = [
    "baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count",
    "speed_to_baseline", "count_to_baseline", "std_to_baseline",
    "prior_speed_mean_3", "prior_count_mean_3", "speed_trend",
    "count_trend", "low_speed_persistence_3",
]
SPATIAL = [
    "neighbor_speed_mean", "neighbor_vehicle_count_mean", "neighbor_occupancy_mean",
    "neighbor_speed_delta", "observed_neighbor_count",
]
FEATURE_VARIANTS: dict[str, list[str]] = {
    "current_only": CURRENT_ONLY,
    "history_current": CURRENT_ONLY + HISTORY,
    "history_spatial": CURRENT_ONLY + HISTORY + SPATIAL,
}


def reject_forbidden_columns(columns: Iterable[str], *, context: str = "feature list") -> None:
    invalid = sorted({column for column in columns if any(token in column.lower() for token in FORBIDDEN_TOKENS)})
    if invalid:
        raise ValueError(f"forbidden columns in {context}: {invalid}")


def feature_schema() -> dict[str, object]:
    classification = {}
    for name in CURRENT_ONLY:
        if name in {"hour_sin", "hour_cos"}:
            classification[name] = "derived"
        elif name in {"road_type_code", "lane_count", "max_speed_kmph"}:
            classification[name] = "current"
        else:
            classification[name] = "current"
    classification.update({name: "historical" if name.startswith(("baseline_", "prior_")) else "derived" for name in HISTORY})
    classification.update({name: "derived" for name in SPATIAL})
    classification.update({name: "metadata" for name in METADATA_COLUMNS})
    return {
        "variants": FEATURE_VARIANTS,
        "classification": classification,
        "metadata": METADATA_COLUMNS,
        "forbidden": list(FORBIDDEN_TOKENS),
        "ordering": "Each variant is an ordered prefix expansion: current_only, history_current, history_spatial.",
        "causality": "Current timestamp and earlier observations only; rolling features are shifted and use strictly prior rows.",
    }


@dataclass(frozen=True)
class TrainScaler:
    mean: Mapping[str, float]
    scale: Mapping[str, float]

    @classmethod
    def fit(cls, frame: pd.DataFrame, columns: list[str]) -> "TrainScaler":
        reject_forbidden_columns(columns)
        values = frame[columns].astype(float)
        means = values.mean()
        scales = values.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
        return cls(means.to_dict(), scales.to_dict())

    def transform(self, frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        if list(self.mean) != columns or list(self.scale) != columns:
            raise ValueError("scaler feature ordering does not match variant")
        result = frame.copy()
        scaled = (result[columns].astype(float) - pd.Series(self.mean)) / pd.Series(self.scale)
        for column in columns:
            result[column] = scaled[column]
        return result

    def as_dict(self) -> dict[str, dict[str, float]]:
        return {"mean": dict(self.mean), "scale": dict(self.scale)}


class CausalFeatureBuilder:
    """Build ordered variants from label-free per-segment/tick state."""

    REQUIRED = {
        "segment_id", "region_id", "timestamp", "avg_speed_kmph", "speed_std_kmph",
        "vehicle_count", "occupancy", "flow_rate_vph", "stopped_fraction",
        "road_type_code", "lane_count", "max_speed_kmph", "is_prehistory",
    }

    def __init__(self, network: CanonicalNetwork) -> None:
        directed: dict[str, set[str]] = defaultdict(set)
        for transition in network.transitions:
            directed[transition.from_segment_id].add(transition.to_segment_id)
        self._neighbors = {key: tuple(sorted(value)) for key, value in directed.items()}
        self._edges = pd.DataFrame(
            [(source, target) for source, targets in self._neighbors.items() for target in targets],
            columns=["segment_id", "neighbor_segment_id"],
        )

    def build(self, states: pd.DataFrame, baselines: pd.DataFrame, *, variant: str) -> pd.DataFrame:
        if variant not in FEATURE_VARIANTS:
            raise ValueError(f"unknown feature variant: {variant}")
        reject_forbidden_columns(states.columns, context="feature source")
        missing = self.REQUIRED - set(states.columns)
        if missing:
            raise ValueError(f"traffic states missing columns: {sorted(missing)}")
        frame = states.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame = frame.sort_values(["segment_id", "timestamp"], kind="stable").reset_index(drop=True)
        deltas = frame.groupby("segment_id", sort=False)["timestamp"].diff().dropna().dt.total_seconds()
        if not deltas.eq(HISTORY_CADENCE_SECONDS).all():
            raise ValueError(f"Geo V2 feature history requires exact {HISTORY_CADENCE_SECONDS}-second cadence")
        hour = frame["timestamp"].dt.hour + frame["timestamp"].dt.minute / 60.0
        frame["hour_sin"] = np.sin(2.0 * math.pi * hour / 24.0)
        frame["hour_cos"] = np.cos(2.0 * math.pi * hour / 24.0)

        baseline_columns = ["segment_id", "baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count"]
        if set(baseline_columns) - set(baselines.columns):
            raise ValueError("baseline table is incomplete")
        frame = frame.merge(baselines[baseline_columns], on="segment_id", how="left", validate="many_to_one")
        if frame[baseline_columns[1:]].isna().any().any():
            raise ValueError("every traffic segment requires normal prehistory")
        frame["speed_to_baseline"] = frame["avg_speed_kmph"] / frame["baseline_speed_kmph"].clip(lower=1.0)
        frame["count_to_baseline"] = frame["vehicle_count"] / frame["baseline_vehicle_count"].clip(lower=0.5)
        frame["std_to_baseline"] = frame["speed_std_kmph"] / frame["baseline_speed_std_kmph"].clip(lower=0.5)

        grouped = frame.groupby("segment_id", sort=False)
        frame["prior_speed_mean_3"] = grouped["avg_speed_kmph"].transform(lambda values: values.shift(1).rolling(3, min_periods=1).mean())
        frame["prior_count_mean_3"] = grouped["vehicle_count"].transform(lambda values: values.shift(1).rolling(3, min_periods=1).mean())
        frame["prior_speed_mean_3"] = frame["prior_speed_mean_3"].fillna(frame["baseline_speed_kmph"])
        frame["prior_count_mean_3"] = frame["prior_count_mean_3"].fillna(frame["baseline_vehicle_count"])
        frame["speed_trend"] = frame["avg_speed_kmph"] - frame["prior_speed_mean_3"]
        frame["count_trend"] = frame["vehicle_count"] - frame["prior_count_mean_3"]
        low_speed = (frame["avg_speed_kmph"] < 0.7 * frame["baseline_speed_kmph"]).astype(float)
        frame["low_speed_persistence_3"] = low_speed.groupby(frame["segment_id"]).transform(
            lambda values: values.shift(1).rolling(3, min_periods=1).mean()
        ).fillna(0.0)

        observations = frame[["timestamp", "segment_id", "avg_speed_kmph", "vehicle_count", "occupancy"]].rename(columns={
            "segment_id": "neighbor_segment_id", "avg_speed_kmph": "neighbor_speed_mean",
            "vehicle_count": "neighbor_vehicle_count_mean", "occupancy": "neighbor_occupancy_mean",
        })
        observed_edges = self._edges.merge(observations, on="neighbor_segment_id", how="inner")
        spatial = observed_edges.groupby(["timestamp", "segment_id"], as_index=False).agg(
            neighbor_speed_mean=("neighbor_speed_mean", "mean"),
            neighbor_vehicle_count_mean=("neighbor_vehicle_count_mean", "mean"),
            neighbor_occupancy_mean=("neighbor_occupancy_mean", "mean"),
            observed_neighbor_count=("neighbor_segment_id", "nunique"),
        )
        frame = frame.merge(spatial, on=["timestamp", "segment_id"], how="left", validate="one_to_one")
        frame[["neighbor_speed_mean", "neighbor_vehicle_count_mean", "neighbor_occupancy_mean", "observed_neighbor_count"]] = frame[[
            "neighbor_speed_mean", "neighbor_vehicle_count_mean", "neighbor_occupancy_mean", "observed_neighbor_count",
        ]].fillna(0.0)
        frame["neighbor_speed_delta"] = frame["avg_speed_kmph"] - frame["neighbor_speed_mean"]

        output = frame.loc[~frame["is_prehistory"].astype(bool), [
            "segment_id", "region_id", "timestamp", *FEATURE_VARIANTS[variant]
        ]].copy()
        reject_forbidden_columns(FEATURE_VARIANTS[variant])
        return output.sort_values(["timestamp", "segment_id"], kind="stable").reset_index(drop=True)
