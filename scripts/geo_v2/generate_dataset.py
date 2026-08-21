"""Generate an additive, reproducible Geo V2 telemetry and feature dataset."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.geo_v2.demo import ScheduledDemo  # noqa: E402
from app.core.constants import EventType  # noqa: E402
from app.services.geo_v2.network import load_overpass_json  # noqa: E402
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig  # noqa: E402
from app.ml.features.windowing import extract_windowed_features  # noqa: E402
from scripts.geo_v2.common import NETWORK_SOURCE, NETWORK_VERSION, write_csv, write_json  # noqa: E402


def _truth(simulation: GeoV2Simulation) -> list[dict[str, object]]:
    return [{
        "event_id": event.event_id, "event_type": event.event_type.value,
        "segment_id": event.segment_id, "severity": event.severity,
        "start_time": event.start_time, "end_time": event.end_time,
    } for event in simulation.events.values()]


def _install_schedule(simulation: GeoV2Simulation, path: Path | None) -> None:
    if path is None:
        ScheduledDemo.install(simulation, simulation.network.segments[0].segment_id)
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for index, item in enumerate(payload["scenarios"], 1):
        simulation.schedule_event(
            EventType(item["type"]), item["segment_id"],
            start_time=simulation.config.start_time + timedelta(seconds=float(item.get("start_offset_seconds", 0))),
            duration_minutes=float(item["duration_seconds"]) / 60,
            severity=float(item.get("severity", 0.7)), event_id=item.get("event_id", f"OFFLINE_{index:04d}"),
        )


def _label_from_truth(row: pd.Series, truth: list[dict[str, object]]) -> str:
    active = [item for item in truth if item["segment_id"] == row["segment_id"] and item["start_time"] <= row["timestamp"] < item["end_time"]]
    return max(active, key=lambda item: (float(item["severity"]), str(item["event_id"])), default={"event_type": "normal"})["event_type"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, choices=(1, 5, 24), default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=datetime.fromisoformat, default=datetime(2026, 7, 7, 6))
    parser.add_argument("--tick-seconds", type=float, default=600)
    parser.add_argument("--vehicle-count", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=ROOT / "data/geo_v2/fedrouteai_dataset_geo_v2")
    parser.add_argument("--osm", type=Path, default=ROOT / "data/geo_v2/beeramguda_roads.osm.json")
    parser.add_argument("--schedule", type=Path, help="JSON schedule; defaults to the five-hour demo")
    args = parser.parse_args()
    network = load_overpass_json(args.osm)
    simulation = GeoV2Simulation(network, SimulationConfig(
        vehicle_count=args.vehicle_count, tick_seconds=1, simulation_speed=args.tick_seconds,
        random_seed=args.seed, start_time=args.start,
    ))
    _install_schedule(simulation, args.schedule)
    truth = _truth(simulation)
    simulation.start()
    ticks = int(args.hours * 3600 / args.tick_seconds)
    telemetry: list[dict[str, object]] = []
    for _ in range(ticks):
        telemetry.extend({**row, "label": "normal", "event_id": ""} for row in simulation.tick())
    simulation.stop()

    output = args.output
    write_csv(output / "raw_telemetry.csv", telemetry)
    write_csv(output / "scenario_ground_truth.csv", truth)
    segments = [{
        "segment_id": segment.segment_id, "region_id": segment.region_id,
        "road_type": segment.road_type.value, "number_of_lanes": segment.lanes,
        "flood_prone": False, "neighbor_segments": "",
    } for segment in network.segments]
    segment_df = pd.DataFrame(segments)
    raw_df = pd.DataFrame(telemetry)
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
    labeled_df = raw_df.copy()
    labeled_df["label"] = labeled_df.apply(lambda row: _label_from_truth(row, truth), axis=1)
    normal_df = labeled_df[labeled_df["label"] == "normal"]
    memory = normal_df.groupby(["segment_id", normal_df["timestamp"].dt.hour]).agg(
        avg_speed_kmph=("speed_kmph", "mean"), std_speed_kmph=("speed_kmph", "std"),
        avg_vehicle_count=("vehicle_id", "nunique"), uturn_rate=("is_uturn_flag", "mean"),
    ).reset_index(names=["segment_id", "hour_of_day"])
    memory["std_speed_kmph"] = memory["std_speed_kmph"].fillna(0)
    memory["sample_size"] = 1
    features = extract_windowed_features(labeled_df, segment_df, memory)
    cutoff = args.start + timedelta(hours=args.hours * 0.7)
    if not features.empty:
        write_csv(output / "feature_windows.csv", features.to_dict("records"))
        for region_number in range(1, 9):
            region_id = f"REGION_{region_number:02d}"
            region_dir = output / "regional_partitions" / region_id
            frame = features[features["region_id"] == region_id]
            write_csv(region_dir / "feature_windows.csv", frame.to_dict("records"))
            write_json(region_dir / "temporal_split_manifest.json", {
                "region_id": region_id, "train_before": cutoff,
                "train_rows": int((frame["window_start"] < cutoff).sum()),
                "test_rows": int((frame["window_start"] >= cutoff).sum()),
            })
        starts = sorted(str(value) for value in features["window_start"].unique())
    else:
        starts = []
    write_json(output / "temporal_split_manifest.json", {
        "train_before": cutoff, "feature_window_count": len(features),
        "train_windows": [value for value in starts if value < str(cutoff)],
        "test_windows": [value for value in starts if value >= str(cutoff)],
        "network_source": NETWORK_SOURCE, "network_version": NETWORK_VERSION,
        "v1_untouched": True,
    })
    write_json(output / "manifest.json", {
        "hours": args.hours, "seed": args.seed, "start": args.start,
        "tick_seconds": args.tick_seconds, "vehicle_count": args.vehicle_count,
        "telemetry_rows": len(telemetry), "scenario_rows": len(truth),
        "feature_windows": len(features), "network_version": NETWORK_VERSION,
        "ground_truth_is_separate": True,
    })
    print(f"wrote {len(telemetry)} telemetry rows and {len(features)} feature windows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
