"""Generate the additive, leakage-resistant Geo V2 ML v1 dataset."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.constants import EventType  # noqa: E402
from app.ml.geo_v2.audit import audit_dataset  # noqa: E402
from app.ml.geo_v2.dataset import (  # noqa: E402
    DATASET_VERSION, LABEL_MAPPING, LABEL_PRIORITY, GeoV2DatasetBuilder, episode_boundaries,
)
from app.ml.geo_v2.features import FEATURE_VARIANTS, feature_schema  # noqa: E402
from app.services.geo_v2.network import CanonicalNetwork, load_overpass_json  # noqa: E402
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig  # noqa: E402
from scripts.geo_v2.common import NETWORK_SOURCE, NETWORK_VERSION, write_json  # noqa: E402


SPLIT_CONFIG = {
    "train": {"seed": 4101, "start": datetime(2026, 7, 7, 6, 0)},
    "validation": {"seed": 5203, "start": datetime(2026, 8, 7, 6, 0)},
    "test": {"seed": 6307, "start": datetime(2026, 9, 7, 6, 0)},
}
EVENT_ORDER = [
    EventType.CONGESTION, EventType.ROAD_DAMAGE, EventType.CONSTRUCTION,
    EventType.FLOOD, EventType.ACCIDENT, EventType.DIVERSION, EventType.ROAD_BLOCK,
]
EVENT_CODES = {
    EventType.CONGESTION: "CGS", EventType.ROAD_DAMAGE: "DMG",
    EventType.CONSTRUCTION: "CST", EventType.FLOOD: "FLD",
    EventType.ACCIDENT: "ACC", EventType.DIVERSION: "DIV",
    EventType.ROAD_BLOCK: "BLK",
}
ROAD_CODES = {"residential": 0, "collector": 1, "arterial": 2, "highway_link": 3}


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def _git_revision() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() or "unknown"


def _directed_neighbors(network: CanonicalNetwork) -> dict[str, set[str]]:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for transition in network.transitions:
        neighbors[transition.from_segment_id].add(transition.to_segment_id)
    return neighbors


def _aggregate_tick(
    observations: list[dict[str, object]],
    network: CanonicalNetwork,
    previous_segments: dict[str, str],
    *,
    is_prehistory: bool,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    arrivals: Counter[str] = Counter()
    for row in observations:
        segment_id = str(row["segment_id"])
        grouped[segment_id].append(row)
        prior = previous_segments.get(str(row["vehicle_id"]))
        if prior is not None and prior != segment_id:
            arrivals[segment_id] += 1
        previous_segments[str(row["vehicle_id"])] = segment_id
    timestamp = observations[0]["timestamp"]
    records = []
    for segment in network.segments:
        items = grouped.get(segment.segment_id, [])
        speeds = pd.Series([float(row["speed_kmph"]) for row in items], dtype=float)
        count = len(items)
        capacity = max(segment.length_m * segment.lanes / 7.5, 1.0)
        records.append({
            "segment_id": segment.segment_id,
            "region_id": segment.region_id,
            "timestamp": timestamp,
            "avg_speed_kmph": float(speeds.mean()) if count else 0.0,
            "speed_std_kmph": float(speeds.std(ddof=0)) if count else 0.0,
            "vehicle_count": count,
            "occupancy": min(count / capacity, 1.0),
            "flow_rate_vph": arrivals[segment.segment_id] * 30.0,
            "stopped_fraction": float((speeds < 2.0).mean()) if count else 0.0,
            "road_type_code": ROAD_CODES[segment.road_type.value],
            "lane_count": segment.lanes,
            "max_speed_kmph": segment.max_speed_kmph,
            "is_prehistory": is_prehistory,
        })
    return records


def _select_segments(network: CanonicalNetwork, prehistory: pd.DataFrame) -> dict[str, list[str]]:
    neighbors = _directed_neighbors(network)
    scores = prehistory.groupby(["region_id", "segment_id"])["vehicle_count"].agg(["mean", "max"])
    selected: dict[str, list[str]] = {}
    for region_number in range(1, 9):
        region = f"REGION_{region_number:02d}"
        candidates = [
            (float(row["mean"]), float(row["max"]), segment_id)
            for (_, segment_id), row in scores.loc[[region]].iterrows()
            if row["max"] > 0 and neighbors.get(segment_id)
        ] if region in scores.index.get_level_values(0) else []
        candidates.sort(reverse=True)
        if not candidates:
            raise RuntimeError(f"warmup found no occupied segment with directed neighbors in {region}")
        selected[region] = [item[2] for item in candidates[: min(3, len(candidates))]]
    return selected


def _baseline(prehistory: pd.DataFrame) -> pd.DataFrame:
    result = prehistory.groupby("segment_id").agg(
        baseline_speed_kmph=("avg_speed_kmph", "mean"),
        baseline_speed_std_kmph=("speed_std_kmph", "mean"),
        baseline_vehicle_count=("vehicle_count", "mean"),
    ).reset_index()
    result["baseline_speed_kmph"] = result["baseline_speed_kmph"].clip(lower=1.0)
    result["baseline_speed_std_kmph"] = result["baseline_speed_std_kmph"].clip(lower=0.5)
    result["baseline_vehicle_count"] = result["baseline_vehicle_count"].clip(lower=0.5)
    return result


def _simulate_split(network: CanonicalNetwork, split: str, seed: int, start: datetime, tick_seconds: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    warmup_ticks = 12
    event_ticks = 14
    gap_ticks = 2
    flood_context = {
        segment.segment_id: {"flood_prone": True, "source": "synthetic_config"}
        for segment in network.segments
    }
    simulation = GeoV2Simulation(network, SimulationConfig(
        vehicle_count=1000, tick_seconds=1.0, simulation_speed=tick_seconds,
        random_seed=seed, start_time=start,
    ), segment_context=flood_context)
    simulation.start()
    raw = []
    state_rows = []
    previous = {}
    for _ in range(warmup_ticks):
        observations = simulation.tick()
        raw.extend({key: value for key, value in row.items() if key not in {"label", "event_id"}} for row in observations)
        state_rows.extend(_aggregate_tick(observations, network, previous, is_prehistory=True))
    selected = _select_segments(network, pd.DataFrame(state_rows))

    truth = []
    split_code = {"train": "TR", "validation": "VA", "test": "TE"}[split]
    for event_index, event_type in enumerate(EVENT_ORDER):
        event_start = simulation.state.current_time + timedelta(seconds=tick_seconds)
        for region_number in range(1, 9):
            region = f"REGION_{region_number:02d}"
            candidates = selected[region]
            segment_id = candidates[event_index % len(candidates)]
            event_id = f"{split_code}_{EVENT_CODES[event_type]}_R{region_number:02d}"
            event = simulation.schedule_event(
                event_type, segment_id, start_time=event_start,
                duration_minutes=event_ticks * tick_seconds / 60.0,
                severity=1.0, event_id=event_id,
            )
            truth.append({
                "event_id": event.event_id, "episode_id": event.event_id,
                "event_type": event.event_type.value, "segment_id": event.segment_id,
                "region_id": region, "severity": event.severity,
                "start_time": event.start_time, "end_time": event.end_time,
                "primary_label_priority": LABEL_PRIORITY.index(event.event_type.value),
                "context_source": "synthetic_config" if event_type is EventType.FLOOD else "none",
            })
        for _ in range(event_ticks + gap_ticks):
            observations = simulation.tick()
            raw.extend({key: value for key, value in row.items() if key not in {"label", "event_id"}} for row in observations)
            state_rows.extend(_aggregate_tick(observations, network, previous, is_prehistory=False))
    simulation.stop()
    states = pd.DataFrame(state_rows)
    raw_frame = pd.DataFrame(raw)
    truth_frame = pd.DataFrame(truth)
    selection = {
        "method": "normal warmup mean occupancy ranking, requiring observed traffic and at least one real outgoing directed graph neighbor",
        "segments_by_region": selected,
        "flood_prone_context": {segment_id: flood_context[segment_id] for ids in selected.values() for segment_id in ids},
        "context_note": "Flood eligibility is synthetic context configured before warmup for all cached-network segments; only warmup-selected occupied segments receive floods. It is not inferred from OSM or exposed as a model feature.",
    }
    return raw_frame, states, _baseline(states[states["is_prehistory"]]), truth_frame, selection


def _measurability(states: dict[str, pd.DataFrame], truths: dict[str, pd.DataFrame]) -> dict[str, object]:
    reports = {}
    failures = []
    for split, frame in states.items():
        target = frame[~frame["is_prehistory"]].copy()
        target["timestamp"] = pd.to_datetime(target["timestamp"])
        split_report = {}
        for event_type in EVENT_ORDER:
            event_rows = []
            for event in truths[split][truths[split]["event_type"] == event_type.value].itertuples(index=False):
                event_rows.append(target[(target["segment_id"] == event.segment_id) & (target["timestamp"] >= event.start_time) & (target["timestamp"] < event.end_time)])
            affected = pd.concat(event_rows, ignore_index=True)
            normal = frame[frame["is_prehistory"] & frame["segment_id"].isin(affected["segment_id"])]
            speed_delta = float(affected["avg_speed_kmph"].mean() - normal["avg_speed_kmph"].mean())
            count_delta = float(affected["vehicle_count"].mean() - normal["vehicle_count"].mean())
            measurable = abs(speed_delta) >= 0.25 or abs(count_delta) >= 0.25
            split_report[event_type.value] = {"rows": len(affected), "mean_speed_delta_kmph": speed_delta, "mean_vehicle_count_delta": count_delta, "measurable": measurable}
            if not measurable:
                failures.append(f"{split}/{event_type.value}")
        reports[split] = split_report
    if failures:
        raise RuntimeError(f"event telemetry effects are not measurable: {failures}")
    return reports


def generate(output: Path, osm: Path, *, tick_seconds: int = 120, audit: bool = True) -> dict[str, object]:
    started = time.monotonic()
    if output.exists() and any(output.iterdir()):
        if (output / "manifest.json").exists():
            raise FileExistsError(f"refusing to overwrite existing dataset: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    network = load_overpass_json(osm)
    raw: dict[str, pd.DataFrame] = {}
    states: dict[str, pd.DataFrame] = {}
    baselines: dict[str, pd.DataFrame] = {}
    truths: dict[str, pd.DataFrame] = {}
    selections = {}
    for split, config in SPLIT_CONFIG.items():
        raw[split], states[split], baselines[split], truths[split], selections[split] = _simulate_split(
            network, split, int(config["seed"]), config["start"], tick_seconds,
        )
        _write_csv(output / "raw_telemetry" / f"{split}.csv", raw[split])
        _write_csv(output / "traffic_states" / f"{split}.csv", states[split])
        _write_csv(output / "scenario_ground_truth" / f"{split}.csv", truths[split])
        _write_csv(output / "normal_prehistory_baselines" / f"{split}.csv", baselines[split])

    result = GeoV2DatasetBuilder(network).build(states, baselines, truths)
    for variant, table in result.tables.items():
        _write_csv(output / "feature_tables" / variant / "all.csv", table)
        for split in SPLIT_CONFIG:
            _write_csv(output / "feature_tables" / variant / f"{split}.csv", table[table["split"] == split])
        for region_number in range(1, 9):
            region = f"REGION_{region_number:02d}"
            region_frame = table[table["region_id"] == region]
            _write_csv(output / "regional_partitions" / region / f"{variant}.csv", region_frame)
            write_json(output / "regional_partitions" / region / "manifest.json", {
                "client_id": region, "dataset_version": DATASET_VERSION,
                "rows_by_variant": {name: int((value["region_id"] == region).sum()) for name, value in result.tables.items()},
                "rows_by_split": region_frame["split"].value_counts().sort_index().to_dict(),
                "duplicated_rows": False,
            })
        write_json(output / "scalers" / f"{variant}.json", {
            "fit_split": "train", "feature_order": FEATURE_VARIANTS[variant], **result.scalers[variant].as_dict(),
        })

    canonical = result.tables["history_spatial"]
    distributions = canonical.groupby(["split", "label"]).size().unstack(fill_value=0)
    minimum_per_split = 100
    insufficient = [f"{split}/{label}={int(distributions.loc[split, label])}" for split in SPLIT_CONFIG for label in LABEL_MAPPING if int(distributions.loc[split, label]) < minimum_per_split]
    if insufficient:
        raise RuntimeError(f"class/window support below {minimum_per_split}: {insufficient}")
    write_json(output / "feature_schema.json", feature_schema())
    write_json(output / "label_mapping.json", {"mapping": LABEL_MAPPING, "primary_label_priority": LABEL_PRIORITY, "priority_rule": "First matching label in this ordered list wins for simultaneous events; event_id is the deterministic tie-breaker."})
    write_json(output / "episode_boundaries.json", episode_boundaries(canonical))
    write_json(output / "segment_selection.json", selections)
    measurability = _measurability(states, truths)
    elapsed = time.monotonic() - started
    manifest = {
        "dataset_version": DATASET_VERSION, "generated_at": datetime.now().isoformat(),
        "git_revision": _git_revision(), "network_source": NETWORK_SOURCE,
        "network_version": NETWORK_VERSION, "osm_cache": str(osm.relative_to(ROOT)),
        "geometry_unchanged": True, "vehicle_count": 1000, "tick_seconds": tick_seconds,
        "splits": {name: {**config, "raw_rows": len(raw[name]), "state_rows": len(states[name]), "truth_episodes": len(truths[name])} for name, config in SPLIT_CONFIG.items()},
        "feature_variants": FEATURE_VARIANTS,
        "class_distributions": distributions.to_dict("index"),
        "episode_count_by_split_label": canonical.groupby(["split", "label"])["episode_id"].nunique().unstack(fill_value=0).to_dict("index"),
        "event_measurability": measurability,
        "normal_prehistory": "Separate normal warmup in each split; target/future rows are excluded. Scalers fit on train only.",
        "truth_join": "Feature construction completes before separate scenario truth is joined.",
        "persistent_vehicle_ids": "Retained only in raw GPS for spatial validation; excluded from aggregate traffic states and all feature lists.",
        "generation_seconds_before_audit": elapsed,
        "existing_geo_v2_dataset_untouched": True,
    }
    write_json(output / "manifest.json", manifest)
    if audit:
        audit_dataset(output, network)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1")
    parser.add_argument("--osm", type=Path, default=ROOT / "data/geo_v2/beeramguda_roads.osm.json")
    parser.add_argument("--tick-seconds", type=int, default=120)
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()
    manifest = generate(args.output, args.osm, tick_seconds=args.tick_seconds, audit=not args.skip_audit)
    print(json.dumps({"output": str(args.output), "class_distributions": manifest["class_distributions"], "generation_seconds": manifest["generation_seconds_before_audit"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
