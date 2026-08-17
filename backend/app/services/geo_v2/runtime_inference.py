"""Causal 27-feature Geo V2 runtime inference and trace construction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Iterable

import math
import numpy as np

from app.ml.geo_v2.features import FEATURE_VARIANTS
from app.ml.geo_v2.model_store import GeoV2ModelStore


FEATURE_VERSION = "geo-v2-history-spatial-27-v1"
ROAD_TYPE_CODES = {"residential": 0, "collector": 1, "arterial": 2, "highway_link": 3}


@dataclass(frozen=True)
class GeoV2Telemetry:
    avg_speed_kmph: float
    speed_std_kmph: float
    vehicle_count: float
    occupancy: float
    flow_rate_vph: float
    stopped_fraction: float


@dataclass(frozen=True)
class GeoV2Context:
    source_id: str
    run_id: str
    segment_id: str
    timestamp: datetime
    telemetry: GeoV2Telemetry
    road_type: str
    lane_count: int
    max_speed_kmph: float
    baseline_speed_kmph: float
    baseline_speed_std_kmph: float
    baseline_vehicle_count: float
    neighbors: tuple[GeoV2Telemetry, ...]
    historical_rows: tuple[dict[str, float], ...] = ()


@dataclass(frozen=True)
class GeoV2RuntimeResult:
    status: str
    model_version: str | None
    prediction: str | None
    confidence: float | None
    probabilities: dict[str, float]
    baseline: dict[str, float]
    deviations: dict[str, float]


class CausalFeatureContextCache:
    """Small process-local supplement for request-order history; DB remains durable source."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], list[dict[str, float]]] = {}
        self._lock = RLock()

    def prior(self, context: GeoV2Context) -> list[dict[str, float]]:
        key = (context.source_id, context.run_id, context.segment_id)
        with self._lock:
            # Durable rows already include prior cached predictions after the
            # preceding request commits. Do not count the same timestamp twice.
            return list(context.historical_rows[-3:]) if context.historical_rows else list(self._rows.get(key, [])[-3:])

    def record(self, context: GeoV2Context, trace: dict[str, float]) -> None:
        key = (context.source_id, context.run_id, context.segment_id)
        with self._lock:
            rows = self._rows.setdefault(key, [])
            rows.append(trace)
            del rows[:-3]


def infer_geo_v2_batch(
    contexts: Iterable[GeoV2Context], store: GeoV2ModelStore, cache: CausalFeatureContextCache,
) -> list[GeoV2RuntimeResult]:
    ordered = list(contexts)
    traces = [_build_trace(context, cache.prior(context)) for context in ordered]
    vectors = np.asarray([[trace[name] for name in FEATURE_VARIANTS["history_spatial"]] for trace in traces], dtype=np.float32)
    outcome = store.predict(vectors)
    results: list[GeoV2RuntimeResult] = []
    for context, trace, probabilities in zip(ordered, traces, outcome.probabilities or [None] * len(ordered), strict=True):
        baseline = {name: trace[name] for name in ("baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count")}
        if outcome.status != "ok" or probabilities is None:
            results.append(GeoV2RuntimeResult("model_unavailable", outcome.model_version, None, None, {}, baseline, trace))
        else:
            prediction = max(probabilities, key=probabilities.get)
            results.append(GeoV2RuntimeResult("ok", outcome.model_version, prediction, probabilities[prediction], probabilities, baseline, trace))
        cache.record(context, trace)
    return results


def _build_trace(context: GeoV2Context, prior: list[dict[str, float]]) -> dict[str, float]:
    current = context.telemetry
    speed_prior = [row["avg_speed_kmph"] for row in prior]
    count_prior = [row["vehicle_count"] for row in prior]
    prior_speed = sum(speed_prior) / len(speed_prior) if speed_prior else context.baseline_speed_kmph
    prior_count = sum(count_prior) / len(count_prior) if count_prior else context.baseline_vehicle_count
    hour = context.timestamp.hour + context.timestamp.minute / 60.0
    neighbors = context.neighbors
    neighbor_speed = sum(item.avg_speed_kmph for item in neighbors) / len(neighbors) if neighbors else 0.0
    neighbor_count = sum(item.vehicle_count for item in neighbors) / len(neighbors) if neighbors else 0.0
    neighbor_occupancy = sum(item.occupancy for item in neighbors) / len(neighbors) if neighbors else 0.0
    return {
        "avg_speed_kmph": current.avg_speed_kmph, "speed_std_kmph": current.speed_std_kmph,
        "vehicle_count": current.vehicle_count, "occupancy": current.occupancy,
        "flow_rate_vph": current.flow_rate_vph, "stopped_fraction": current.stopped_fraction,
        "hour_sin": math.sin(2 * math.pi * hour / 24), "hour_cos": math.cos(2 * math.pi * hour / 24),
        "road_type_code": float(ROAD_TYPE_CODES.get(context.road_type.lower(), 0)), "lane_count": float(context.lane_count),
        "max_speed_kmph": context.max_speed_kmph, "baseline_speed_kmph": context.baseline_speed_kmph,
        "baseline_speed_std_kmph": context.baseline_speed_std_kmph, "baseline_vehicle_count": context.baseline_vehicle_count,
        "speed_to_baseline": current.avg_speed_kmph / max(context.baseline_speed_kmph, 1.0),
        "count_to_baseline": current.vehicle_count / max(context.baseline_vehicle_count, 0.5),
        "std_to_baseline": current.speed_std_kmph / max(context.baseline_speed_std_kmph, 0.5),
        "prior_speed_mean_3": prior_speed, "prior_count_mean_3": prior_count,
        "speed_trend": current.avg_speed_kmph - prior_speed, "count_trend": current.vehicle_count - prior_count,
        "low_speed_persistence_3": sum(value < 0.7 * context.baseline_speed_kmph for value in speed_prior) / len(speed_prior) if speed_prior else 0.0,
        "neighbor_speed_mean": neighbor_speed, "neighbor_vehicle_count_mean": neighbor_count,
        "neighbor_occupancy_mean": neighbor_occupancy, "neighbor_speed_delta": current.avg_speed_kmph - neighbor_speed,
        "observed_neighbor_count": float(len(neighbors)),
    }
