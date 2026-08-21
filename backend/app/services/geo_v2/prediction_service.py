"""Repository-backed façade for the additive Geo V2 runtime API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.ml.geo_v2.model_store import GEO_V2_MODEL_STORE, GeoV2ModelStore
from app.repositories.geo_v2_repository import GeoV2Repository
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.segment_repository import SegmentRepository
from app.schemas.geo_v2_inference import GeoV2InferenceItem
from app.services.geo_v2.runtime_inference import (
    CausalFeatureContextCache, GeoV2Context, GeoV2RuntimeResult, GeoV2Telemetry, infer_geo_v2_batch,
)


@dataclass(frozen=True)
class GeoV2Baseline:
    avg_speed_kmph: float
    std_speed_kmph: float
    avg_vehicle_count: float


class GeoV2PredictionService:
    def __init__(
        self,
        segments: SegmentRepository,
        baselines: HistoricalMemoryRepository,
        predictions: GeoV2Repository,
        store: GeoV2ModelStore = GEO_V2_MODEL_STORE,
        cache: CausalFeatureContextCache | None = None,
    ) -> None:
        self.segments = segments
        self.baselines = baselines
        self.predictions = predictions
        self.store = store
        self.cache = cache or CausalFeatureContextCache()

    def infer_batch(
        self,
        items: list[GeoV2InferenceItem],
        baseline_overrides: dict[str, GeoV2Baseline] | None = None,
    ) -> list[tuple[GeoV2InferenceItem, str, GeoV2RuntimeResult]]:
        contexts: list[GeoV2Context] = []
        regions: list[str] = []
        baseline_overrides = baseline_overrides or {}
        canonical_baselines = _canonical_baselines(settings.GEO_V2_BASELINE_PATH)
        segments = self.segments.get_many({item.segment_id for item in items})
        baselines = self.baselines.get_baselines({
            (item.segment_id, item.as_of.hour) for item in items if item.segment_id not in baseline_overrides
        })
        history_groups: dict[tuple[str, str, datetime], set[str]] = {}
        for item in items:
            history_groups.setdefault((item.source_id, item.run_id, item.as_of), set()).add(item.segment_id)
        histories = {
            group: self.predictions.prediction_histories(group[0], group[1], segment_ids, group[2])
            for group, segment_ids in history_groups.items()
        }
        item_by_segment = {item.segment_id: item for item in items}
        network_version = getattr(self.store, "network_version", None)
        if network_version:
            outgoing = self.predictions.outgoing_neighbors(set(item_by_segment), network_version)
        else:
            transitions = self.predictions.transitions_for_segments(set(item_by_segment))
            outgoing: dict[str, set[str]] = {}
            for transition in transitions:
                outgoing.setdefault(transition.from_segment_id, set()).add(transition.to_segment_id)
        for item in items:
            segment = segments.get(item.segment_id)
            if segment is None:
                raise LookupError(f"Segment {item.segment_id} not found")
            baseline = baseline_overrides.get(item.segment_id) or canonical_baselines.get(item.segment_id)
            if baseline is None and not getattr(self.store, "feature_version", None):
                baseline = baselines.get((item.segment_id, item.as_of.hour))
            if baseline is None:
                raise LookupError(f"Canonical Geo V2 baseline for segment {item.segment_id} not found")
            history = [
                row.current_deviation
                for row in reversed(histories[(item.source_id, item.run_id, item.as_of)].get(item.segment_id, []))
            ]
            telemetry = _telemetry(item.telemetry)
            neighbors = tuple(
                _telemetry(item_by_segment[neighbor_id].telemetry)
                for neighbor_id in sorted(outgoing.get(item.segment_id, ()))
                if neighbor_id in item_by_segment
            )
            contexts.append(GeoV2Context(
                item.source_id, item.run_id, item.segment_id, item.as_of, telemetry,
                segment.road_type, segment.number_of_lanes, segment.max_speed_kmph,
                baseline.avg_speed_kmph, baseline.std_speed_kmph, baseline.avg_vehicle_count,
                neighbors, tuple(history),
            ))
            regions.append(segment.region_id)
        results = infer_geo_v2_batch(contexts, self.store, self.cache)
        rows = []
        for item, result in zip(items, results, strict=True):
            rows.append({
                "source_id": item.source_id, "run_id": item.run_id, "segment_id": item.segment_id,
                "timestamp": item.as_of, "predicted_label": result.prediction, "confidence": result.confidence,
                "class_probabilities": result.probabilities, "model_version": result.model_version or "model-unavailable",
                "historical_baseline": {**result.baseline, "feature_version": getattr(self.store, "feature_version", None) or "geo-v2-history-spatial-27-v1"},
                "current_deviation": {**result.deviations, "inference_status": result.status},
            })
        self.predictions.save_predictions(rows)
        return list(zip(items, regions, results, strict=True))


def _telemetry(value) -> GeoV2Telemetry:
    return GeoV2Telemetry(
        avg_speed_kmph=value.avg_speed_kmph, speed_std_kmph=value.speed_std_kmph,
        vehicle_count=value.vehicle_count, occupancy=value.occupancy,
        flow_rate_vph=value.flow_rate_vph, stopped_fraction=value.stopped_fraction,
    )


@lru_cache(maxsize=4)
def _canonical_baselines(configured_path: str) -> dict[str, GeoV2Baseline]:
    path = Path(configured_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    if not path.is_file():
        return {}
    frame = pd.read_csv(path, usecols=[
        "segment_id", "baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count",
    ])
    return {
        str(row.segment_id): GeoV2Baseline(
            float(row.baseline_speed_kmph), float(row.baseline_speed_std_kmph), float(row.baseline_vehicle_count),
        )
        for row in frame.itertuples(index=False)
    }
