"""Causal 27-feature Geo V2 runtime inference and trace construction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Iterable

import numpy as np

from app.ml.geo_v2.feature_contract import build_feature_trace
from app.ml.geo_v2.model_store import GeoV2ModelStore


FEATURE_VERSION = "geo-v2-causal-120s-v2"


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
            durable = list(context.historical_rows) if context.historical_rows else []
            cached = list(self._rows.get(key, []))
            combined = {int(row["_timestamp"]): row for row in [*cached, *durable] if "_timestamp" in row}
            return [combined[key] for key in sorted(combined)]

    def record(self, context: GeoV2Context, trace: dict[str, float]) -> None:
        key = (context.source_id, context.run_id, context.segment_id)
        with self._lock:
            rows = self._rows.setdefault(key, [])
            timestamp = int(trace["_timestamp"])
            rows[:] = [row for row in rows if int(row["_timestamp"]) != timestamp]
            rows.append(trace)
            rows.sort(key=lambda row: row["_timestamp"])
            del rows[:-3]


def infer_geo_v2_batch(
    contexts: Iterable[GeoV2Context], store: GeoV2ModelStore, cache: CausalFeatureContextCache,
) -> list[GeoV2RuntimeResult]:
    ordered = list(contexts)
    traces = [_build_trace(context, cache.prior(context)) for context in ordered]
    feature_order = getattr(store, "feature_order", ())
    if not feature_order:
        from app.ml.geo_v2.features import FEATURE_VARIANTS
        feature_order = tuple(FEATURE_VARIANTS["history_spatial"])
    vectors = np.asarray([[trace[name] for name in feature_order] for trace in traces], dtype=np.float32)
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
    current = context.telemetry.__dict__
    neighbors = [item.__dict__ for item in context.neighbors]
    return build_feature_trace(
        timestamp=context.timestamp, current=current, road_type=context.road_type,
        lane_count=context.lane_count, max_speed_kmph=context.max_speed_kmph,
        baseline_speed_kmph=context.baseline_speed_kmph,
        baseline_speed_std_kmph=context.baseline_speed_std_kmph,
        baseline_vehicle_count=context.baseline_vehicle_count, prior_rows=prior, neighbors=neighbors,
    )
