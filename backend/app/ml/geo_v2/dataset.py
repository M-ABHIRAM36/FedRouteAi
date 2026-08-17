"""Dataset assembly after label-free Geo V2 feature construction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

import pandas as pd

from app.core.constants import EventType
from app.ml.geo_v2.features import FEATURE_VARIANTS, METADATA_COLUMNS, CausalFeatureBuilder, TrainScaler, reject_forbidden_columns


DATASET_VERSION = "geo_v2_ml_v1"
LABEL_PRIORITY = [
    EventType.ROAD_BLOCK.value, EventType.FLOOD.value, EventType.ACCIDENT.value,
    EventType.CONSTRUCTION.value, EventType.ROAD_DAMAGE.value,
    EventType.DIVERSION.value, EventType.CONGESTION.value, EventType.NORMAL.value,
]
LABEL_MAPPING = {label: index for index, label in enumerate(reversed(LABEL_PRIORITY))}


def join_targets(features: pd.DataFrame, truth: pd.DataFrame, split: str) -> pd.DataFrame:
    """Join targets after features exist, resolving combinations deterministically."""
    result = features.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"])
    events = truth.copy()
    if not events.empty:
        events["start_time"] = pd.to_datetime(events["start_time"])
        events["end_time"] = pd.to_datetime(events["end_time"])
    priority = {label: index for index, label in enumerate(LABEL_PRIORITY)}
    result["label"] = EventType.NORMAL.value
    result["episode_id"] = f"{split}_NORMAL_RUN"
    # Scenario schedule order can contain combinations. Apply in reverse
    # priority so a later, higher-priority assignment deterministically wins.
    for event in sorted(events.to_dict("records"), key=lambda item: (priority[str(item["event_type"])], str(item["event_id"])), reverse=True):
        active = (
            (result["segment_id"] == event["segment_id"])
            & (result["timestamp"] >= event["start_time"])
            & (result["timestamp"] < event["end_time"])
        )
        result.loc[active, "label"] = str(event["event_type"])
        result.loc[active, "episode_id"] = str(event["event_id"])
    result.insert(0, "row_id", [f"{split}_{index:09d}" for index in range(len(result))])
    result.insert(1, "split", split)
    episode = result.pop("episode_id")
    result.insert(2, "episode_id", episode)
    result["label_idx"] = result["label"].map(LABEL_MAPPING)
    return result


@dataclass
class GeoV2DatasetResult:
    tables: dict[str, pd.DataFrame]
    scalers: dict[str, TrainScaler]


class GeoV2DatasetBuilder:
    def __init__(self, network) -> None:
        self.features = CausalFeatureBuilder(network)

    def build(
        self,
        states: Mapping[str, pd.DataFrame],
        baselines: Mapping[str, pd.DataFrame],
        truths: Mapping[str, pd.DataFrame],
    ) -> GeoV2DatasetResult:
        if tuple(states) != ("train", "validation", "test"):
            raise ValueError("splits must be ordered train, validation, test")
        tables: dict[str, pd.DataFrame] = {}
        scalers: dict[str, TrainScaler] = {}
        full_features = {
            split: self.features.build(states[split], baselines[split], variant="history_spatial")
            for split in states
        }
        labeled_features = {
            split: join_targets(full_features[split], truths[split], split)
            for split in states
        }
        for variant, columns in FEATURE_VARIANTS.items():
            reject_forbidden_columns(columns)
            unscaled = {
                split: labeled_features[split][[*METADATA_COLUMNS, *columns, "label", "label_idx"]].copy()
                for split in states
            }
            scaler = TrainScaler.fit(unscaled["train"], columns)
            scalers[variant] = scaler
            scaled_parts = []
            for split in states:
                transformed = scaler.transform(unscaled[split], columns)
                transformed = transformed[[*METADATA_COLUMNS, *columns, "label", "label_idx"]]
                scaled_parts.append(transformed)
            tables[variant] = pd.concat(scaled_parts, ignore_index=True)
        return GeoV2DatasetResult(tables, scalers)


def episode_boundaries(table: pd.DataFrame) -> list[dict[str, object]]:
    grouped = table.groupby(["split", "episode_id", "label"], sort=True)["timestamp"]
    return [
        {"split": split, "episode_id": episode, "label": label, "start": values.min(), "end": values.max(), "rows": int(values.size)}
        for (split, episode, label), values in grouped
    ]
