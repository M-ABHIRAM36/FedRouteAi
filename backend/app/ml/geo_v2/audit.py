"""Strict audit checks for generated Geo V2 ML artifacts."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Mapping
import json
import math

import pandas as pd

from app.core.constants import EventType
from app.ml.geo_v2.features import FEATURE_VARIANTS, FORBIDDEN_TOKENS, reject_forbidden_columns
from app.services.geo_v2.alignment import spatial_alignment_report
from app.services.geo_v2.network import CanonicalNetwork


def audit_split_episode_leakage(table: pd.DataFrame) -> list[str]:
    errors = []
    episode_splits = table.groupby("episode_id")["split"].nunique()
    if (episode_splits > 1).any():
        errors.append(f"episodes cross splits: {sorted(episode_splits[episode_splits > 1].index)}")
    boundaries = table.groupby("split")["timestamp"].agg(["min", "max"])
    for first, second in zip(("train", "validation"), ("validation", "test")):
        if first in boundaries.index and second in boundaries.index and boundaries.loc[first, "max"] >= boundaries.loc[second, "min"]:
            errors.append(f"timestamp overlap between {first} and {second}")
    return errors


def audit_feature_table(table: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    errors = []
    try:
        reject_forbidden_columns(feature_columns)
    except ValueError as exc:
        errors.append(str(exc))
    missing = set(feature_columns) - set(table.columns)
    if missing:
        errors.append(f"missing feature columns: {sorted(missing)}")
        return errors
    numeric = table[feature_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        errors.append("missing or nonnumeric feature values")
    if not numeric.map(math.isfinite).all().all():
        errors.append("nonfinite feature values")
    if table["row_id"].duplicated().any():
        errors.append("duplicate row_id values")
    duplicate_keys = table.duplicated(["split", "segment_id", "timestamp"])
    if duplicate_keys.any():
        errors.append("duplicate split/segment/timestamp rows")
    errors.extend(audit_split_episode_leakage(table))
    expected = {item.value for item in EventType}
    for split, part in table.groupby("split"):
        absent = expected - set(part["label"])
        if absent:
            errors.append(f"{split} missing labels: {sorted(absent)}")
    return errors


def audit_dataset(output: Path, network: CanonicalNetwork) -> dict[str, object]:
    schema = json.loads((output / "feature_schema.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    reports = {}
    client_distributions: dict[str, dict[str, object]] = {}
    all_row_sets = {}
    for variant, columns in FEATURE_VARIANTS.items():
        if schema["variants"].get(variant) != columns:
            errors.append(f"schema ordering mismatch for {variant}")
        table = pd.read_csv(output / "feature_tables" / variant / "all.csv", parse_dates=["timestamp"])
        variant_errors = audit_feature_table(table, columns)
        errors.extend(f"{variant}: {item}" for item in variant_errors)
        reports[variant] = {
            "rows": len(table),
            "class_distribution": table.groupby(["split", "label"]).size().unstack(fill_value=0).to_dict("index"),
            "feature_ranges": {column: {"min": float(table[column].min()), "max": float(table[column].max())} for column in columns},
        }
        all_row_sets[variant] = set(table["row_id"])
        regional_ids = []
        for region_number in range(1, 9):
            region = f"REGION_{region_number:02d}"
            part = pd.read_csv(output / "regional_partitions" / region / f"{variant}.csv")
            if not (part["region_id"] == region).all():
                errors.append(f"{variant}: wrong rows in {region} partition")
            regional_ids.extend(part["row_id"].tolist())
            if variant == "history_spatial":
                client_distributions[region] = {
                    "rows": len(part),
                    "by_split": part["split"].value_counts().sort_index().to_dict(),
                    "by_label": part["label"].value_counts().sort_index().to_dict(),
                }
        if Counter(regional_ids) != Counter(table["row_id"]):
            errors.append(f"{variant}: regional partitions duplicate or omit rows")
    if len({frozenset(values) for values in all_row_sets.values()}) != 1:
        errors.append("variant row identities differ")

    gps_reports = {}
    split_times = {}
    split_vehicles = {}
    split_segments = {}
    for split in ("train", "validation", "test"):
        raw = pd.read_csv(output / "raw_telemetry" / f"{split}.csv", parse_dates=["timestamp"])
        if raw.isna().any().any():
            errors.append(f"{split}: raw GPS has missing values")
        if raw["observation_id"].duplicated().any():
            errors.append(f"{split}: duplicate raw observation_id values")
        numeric = raw[["lat", "lon", "speed_kmph", "heading_deg"]].apply(pd.to_numeric, errors="coerce")
        if numeric.isna().any().any() or not numeric.map(math.isfinite).all().all():
            errors.append(f"{split}: raw GPS has nonfinite numeric values")
        if not raw["lat"].between(-90, 90).all() or not raw["lon"].between(-180, 180).all():
            errors.append(f"{split}: invalid GPS ranges")
        if not raw["speed_kmph"].between(0, 200).all() or not raw["heading_deg"].between(0, 360).all():
            errors.append(f"{split}: invalid speed or heading ranges")
        spatial = spatial_alignment_report(raw.to_dict("records"), network, valid_tolerance_m=1.0)
        if spatial.invalid:
            errors.append(f"{split}: {spatial.invalid} GPS points fail geometry alignment")
        gps_reports[split] = {"rows": len(raw), "valid": spatial.valid, "invalid": spatial.invalid, "max_distance_m": spatial.max_m}
        split_times[split] = (raw["timestamp"].min(), raw["timestamp"].max())
        split_vehicles[split] = set(raw["vehicle_id"])
        split_segments[split] = set(raw["segment_id"])
    for first, second in zip(("train", "validation"), ("validation", "test")):
        if split_times[first][1] >= split_times[second][0]:
            errors.append(f"raw timestamp overlap between {first} and {second}")

    report = {
        "status": "failed" if errors else "passed", "errors": errors,
        "features": reports, "gps": gps_reports,
        "client_distributions": client_distributions,
        "persistent_vehicle_ids": {
            "overlap_across_splits": {"train_validation": len(split_vehicles["train"] & split_vehicles["validation"]), "validation_test": len(split_vehicles["validation"] & split_vehicles["test"])},
            "explanation": "GeoV2Simulation intentionally uses persistent IDs within and across seeded runs. IDs are retained only for raw spatial/trajectory validation and are excluded from every aggregate state and model feature list.",
        },
        "segment_overlap": {"all_splits": len(set.intersection(*split_segments.values()))},
    }
    (output / "audit_report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    if errors:
        raise ValueError("Geo V2 ML audit failed: " + "; ".join(errors))
    return report
