"""Run Geo V2 simulation telemetry through the live API without truth leakage."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
import sys
import time

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.geo_v2_repository import GeoV2Repository  # noqa: E402
from app.repositories.historical_memory_repository import HistoricalMemoryRepository  # noqa: E402
from app.services.geo_v2.demo import ScheduledDemo  # noqa: E402
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig  # noqa: E402
from app.services.live_ingestion.client import LiveIngestionClient  # noqa: E402
from app.repositories.segment_repository import SegmentRepository  # noqa: E402
from app.schemas.geo_v2_inference import GeoV2InferenceItem  # noqa: E402
from app.services.geo_v2.prediction_service import GeoV2Baseline, GeoV2PredictionService  # noqa: E402
from app.services.geo_v2.runtime_inference import CausalFeatureContextCache  # noqa: E402
from scripts.geo_v2.common import NETWORK_SOURCE, NETWORK_VERSION, scrub_observations  # noqa: E402


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


def _load_prior_baselines(baseline_path: Path) -> dict[str, GeoV2Baseline]:
    """Load separate normal-only V2 prehistory without modifying V1 memory."""
    frame = pd.read_csv(baseline_path)
    return {
        str(row.segment_id): GeoV2Baseline(
            avg_speed_kmph=float(row.baseline_speed_kmph),
            std_speed_kmph=float(row.baseline_speed_std_kmph),
            avg_vehicle_count=float(row.baseline_vehicle_count),
        )
        for row in frame.itertuples(index=False)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--source-id", default="geo-v2-demo")
    parser.add_argument("--run-id", default="geo-v2-demo-5h")
    parser.add_argument("--ticks", type=int, default=150)
    parser.add_argument("--vehicle-count", type=int, default=1000)
    parser.add_argument("--tick-seconds", type=float, default=120)
    parser.add_argument("--start", type=datetime.fromisoformat, help="simulation start; defaults to current UTC")
    parser.add_argument("--wall-delay", type=float, default=0)
    parser.add_argument("--local-demo-schedule", action="store_true")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1/normal_prehistory_baselines/train.csv",
    )
    args = parser.parse_args()
    db = SessionLocal()
    network = GeoV2Repository(db).load_network(NETWORK_VERSION)
    if not network.segments:
        db.close()
        raise SystemExit(
            f"Geo V2 network {NETWORK_VERSION!r} is not imported; "
            "run scripts/geo_v2/import_network.py first"
        )
    prior_baselines = _load_prior_baselines(args.baseline)
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
    context_cache = CausalFeatureContextCache()
    prediction_service = GeoV2PredictionService(
        SegmentRepository(db), HistoricalMemoryRepository(db), GeoV2Repository(db), cache=context_cache,
    )
    timing = {"inference_ms": 0.0, "persistence_ms": 0.0}
    predict = prediction_service.store.predict
    persist = prediction_service.predictions.save_predictions

    def timed_predict(rows):
        started = time.perf_counter()
        result = predict(rows)
        timing["inference_ms"] = (time.perf_counter() - started) * 1000
        return result

    def timed_persist(rows):
        started = time.perf_counter()
        result = persist(rows)
        timing["persistence_ms"] = (time.perf_counter() - started) * 1000
        return result

    prediction_service.store.predict = timed_predict
    prediction_service.predictions.save_predictions = timed_persist
    outgoing: dict[str, set[str]] = defaultdict(set)
    for transition in network.transitions:
        outgoing[transition.from_segment_id].add(transition.to_segment_id)
    try:
        with httpx.Client(timeout=30) as http:
            for tick in range(1, args.ticks + 1):
                scenarios = _poll_scenarios(http, args.base_url, args.source_id, args.run_id, simulation.state.current_time)
                _sync_scenarios(simulation, scenarios)
                clean = scrub_observations(simulation.tick())
                ingestion_started = time.perf_counter()
                receipt = ingestion.ingest(tick, clean)
                ingestion_ms = (time.perf_counter() - ingestion_started) * 1000
                # Predict from state at T using only history strictly before T.
                # Scenario labels are absent from clean telemetry and never form a feature.
                prediction_items = []
                observed_states = {
                    segment_id: state
                    for segment_id, state in simulation.state.flow_states.items()
                    if state.vehicle_count > 0
                }
                for segment_id, state in observed_states.items():
                    neighbors = [
                        observed_states[item]
                        for item in sorted(outgoing.get(segment_id, ()))
                        if item in observed_states
                    ]
                    prediction_items.append(GeoV2InferenceItem.model_validate({
                        "source_id": args.source_id,
                        "run_id": args.run_id,
                        "segment_id": segment_id,
                        "as_of": simulation.state.current_time,
                        "telemetry": {
                            "avg_speed_kmph": state.average_speed_kmph,
                            "speed_std_kmph": state.speed_variance ** 0.5,
                            "vehicle_count": state.vehicle_count,
                            "occupancy": state.occupancy,
                            "flow_rate_vph": state.flow_rate_vph,
                            "stopped_fraction": 1.0 if state.average_speed_kmph < 1.0 else 0.0,
                        },
                        "neighbors": [{
                            "segment_id": neighbor.segment_id,
                            "avg_speed_kmph": neighbor.average_speed_kmph,
                            "speed_std_kmph": neighbor.speed_variance ** 0.5,
                            "vehicle_count": neighbor.vehicle_count,
                            "occupancy": neighbor.occupancy,
                            "flow_rate_vph": neighbor.flow_rate_vph,
                            "stopped_fraction": 1.0 if neighbor.average_speed_kmph < 1.0 else 0.0,
                        } for neighbor in neighbors],
                    }))
                prediction_started = time.perf_counter()
                results = prediction_service.infer_batch(prediction_items, baseline_overrides=prior_baselines)
                prediction_ms = (time.perf_counter() - prediction_started) * 1000

                # infer_batch records and persists this tick only after inference,
                # making it eligible as temporal context for the next tick.
                available = sum(result.status == "ok" for _, _, result in results)
                print(
                    f"tick={tick} timestamp={simulation.state.current_time.isoformat()} accepted={receipt['accepted']} "
                    f"observed_segments={len(results)} active_scenarios={len(scenarios)} predictions={available}/{len(results)} "
                    f"ingestion_ms={ingestion_ms:.3f} inference_ms={timing['inference_ms']:.3f} "
                    f"persistence_ms={timing['persistence_ms']:.3f} prediction_persistence_ms={prediction_ms:.3f}"
                )
                if args.wall_delay:
                    time.sleep(args.wall_delay)
    finally:
        simulation.stop()
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
