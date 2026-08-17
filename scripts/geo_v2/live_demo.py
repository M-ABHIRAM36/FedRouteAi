"""Run Geo V2 simulation telemetry through the live API without truth leakage."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.geo_v2_repository import GeoV2Repository  # noqa: E402
from app.repositories.historical_memory_repository import HistoricalMemoryRepository  # noqa: E402
from app.services.federated_learning.global_model import GLOBAL_MODEL_STORE  # noqa: E402
from app.services.geo_v2.demo import ScheduledDemo  # noqa: E402
from app.services.geo_v2.inference import HistoricalBaseline, SegmentContext, infer_telemetry_state  # noqa: E402
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig  # noqa: E402
from app.services.historical_memory.aggregator import build_hourly_profile  # noqa: E402
from app.services.live_ingestion.client import LiveIngestionClient  # noqa: E402
from scripts.geo_v2.common import NETWORK_SOURCE, NETWORK_VERSION, aggregate_observations, scrub_observations  # noqa: E402


def _poll_scenarios(client: httpx.Client, base_url: str, source_id: str, run_id: str, at: datetime) -> list[dict]:
    response = client.get(
        f"{base_url.rstrip('/')}/api/v1/live-scenarios",
        params={"source_id": source_id, "run_id": run_id, "at": at.isoformat()},
    )
    response.raise_for_status()
    return response.json()


def _sync_scenarios(simulation: GeoV2Simulation, scenarios: list[dict]) -> None:
    for item in scenarios:
        if item["event_id"] in simulation.events:
            continue
        ends = datetime.fromisoformat(item["end_time"])
        remaining_minutes = (ends - simulation.state.current_time).total_seconds() / 60
        if remaining_minutes > 0:
            simulation.schedule_event(
                item["event_type"], item["primary_segment_id"],
                start_time=simulation.state.current_time, duration_minutes=remaining_minutes,
                severity=float(item["severity"]), event_id=item["event_id"],
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--source-id", default="geo-v2-demo")
    parser.add_argument("--run-id", default="geo-v2-demo-5h")
    parser.add_argument("--ticks", type=int, default=30)
    parser.add_argument("--vehicle-count", type=int, default=1000)
    parser.add_argument("--tick-seconds", type=float, default=600)
    parser.add_argument("--start", type=datetime.fromisoformat, help="simulation start; defaults to current UTC")
    parser.add_argument("--wall-delay", type=float, default=0)
    parser.add_argument("--local-demo-schedule", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    network = GeoV2Repository(db).load_network(NETWORK_VERSION)
    if not network.segments:
        db.close()
        raise SystemExit(
            f"Geo V2 network {NETWORK_VERSION!r} is not imported; "
            "run scripts/geo_v2/import_network.py first"
        )
    simulation = GeoV2Simulation(network, SimulationConfig(
        vehicle_count=args.vehicle_count, tick_seconds=1, simulation_speed=args.tick_seconds,
        start_time=args.start or datetime.now(UTC).replace(tzinfo=None),
    ))
    if args.local_demo_schedule:
        ScheduledDemo.install(simulation, network.segments[0].segment_id)
    simulation.start()
    ingestion = LiveIngestionClient(
        args.base_url, args.api_key, args.source_id, args.run_id,
        network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
    )
    segments = {segment.segment_id: segment for segment in network.segments}
    normal_history: dict[tuple[str, int], list[SimpleNamespace]] = defaultdict(list)
    try:
        with httpx.Client(timeout=30) as http:
            for tick in range(1, args.ticks + 1):
                scenarios = _poll_scenarios(http, args.base_url, args.source_id, args.run_id, simulation.state.current_time)
                _sync_scenarios(simulation, scenarios)
                clean = scrub_observations(simulation.tick())
                receipt = ingestion.ingest(tick, clean)
                active_segments = {
                    segment_id
                    for item in scenarios
                    for segment_id in item.get("affected_segment_ids", [item["primary_segment_id"]])
                }
                for row in clean:
                    if row["segment_id"] not in active_segments:
                        normal_history[(str(row["segment_id"]), simulation.state.current_time.hour)].append(SimpleNamespace(
                            speed_kmph=row["speed_kmph"], vehicle_id=row["vehicle_id"],
                            is_uturn_flag=row.get("is_uturn_flag", False), timestamp=row["timestamp"],
                        ))
                memory_repo = HistoricalMemoryRepository(db)
                profiles = {}
                profile_updates = []
                for key, history in normal_history.items():
                    profile = build_hourly_profile(key[0], key[1], history)
                    if profile is not None:
                        profiles[key] = profile
                        profile_updates.append(profile)
                memory_repo.upsert_many(profile_updates)
                geo_repo = GeoV2Repository(db)
                predictions = []
                for segment_id, telemetry in aggregate_observations(clean).items():
                    profile = profiles.get((segment_id, simulation.state.current_time.hour))
                    if profile is None:
                        continue
                    segment = segments[segment_id]
                    prediction = infer_telemetry_state(
                        telemetry,
                        HistoricalBaseline(profile.avg_speed_kmph, profile.std_speed_kmph, profile.avg_vehicle_count, profile.uturn_rate, profile.sample_size),
                        SegmentContext(simulation.state.current_time.hour, segment.road_type.value, segment.lanes, False),
                        (), GLOBAL_MODEL_STORE,
                    )
                    predictions.append({
                        "source_id": args.source_id, "run_id": args.run_id, "segment_id": segment_id,
                        "timestamp": simulation.state.current_time, "predicted_label": prediction.prediction,
                        "confidence": prediction.confidence, "class_probabilities": prediction.probabilities,
                        "model_version": prediction.model_version, "historical_baseline": prediction.baseline,
                        "current_deviation": prediction.deviations,
                    })
                geo_repo.save_predictions(predictions)
                print(f"tick={tick} accepted={receipt['accepted']} active_scenarios={len(scenarios)} predictions={len(predictions)}")
                if args.wall_delay:
                    time.sleep(args.wall_delay)
    finally:
        simulation.stop()
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
