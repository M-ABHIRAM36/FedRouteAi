"""Run and verify live simulator ingestion against the configured database."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "dataset_generator"))

from sqlalchemy import text  # noqa: E402

from road_network import build_road_network  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import segment, region, gps_ping, event, historical_memory, fl_round_record, live_ingestion  # noqa: F401, E402
from app.repositories.live_ingestion_repository import LiveIngestionRepository  # noqa: E402
from app.schemas.gps_ping import LiveGPSBatchIn  # noqa: E402
from app.services.live_ingestion.client import LiveIngestionClient  # noqa: E402
from app.services.live_ingestion.service import ingest_live_batch  # noqa: E402
from app.services.live_simulation import LiveTrafficSimulation, SimulationConfig  # noqa: E402


def _payload(batch: list[dict], tick: int, run_id: str) -> dict:
    return {
        "source_id": "manual-live-verification",
        "run_id": run_id,
        "batch_id": f"tick-{tick:08d}",
        "tick_number": tick,
        "observations": [
            {"observation_id": f"{tick}:{row['vehicle_id']}", **row}
            for row in batch
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=10)
    parser.add_argument("--pings", type=int, default=1000)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--event", default="accident")
    args = parser.parse_args()

    segments, _ = build_road_network(seed=42)
    simulation = LiveTrafficSimulation(
        list(segments.itertuples(index=False)),
        SimulationConfig(pings_per_tick=args.pings, random_seed=42),
    )
    simulation.start()
    event_segment = max(
        simulation.state.road_segment_states,
        key=lambda segment_id: simulation.state.road_segment_states[segment_id].vehicle_count,
    )
    simulation.add_event(args.event, event_segment, duration_minutes=30)
    client = LiveIngestionClient(
        args.url,
        args.api_key,
        "manual-live-verification",
        args.run_id,
    ) if args.url else None

    results = []
    for tick in range(1, args.ticks + 1):
        batch = simulation.tick()
        if client:
            result = client.ingest(tick, batch)
        else:
            db = SessionLocal()
            try:
                result = ingest_live_batch(
                    LiveGPSBatchIn.model_validate(_payload(batch, tick, args.run_id)),
                    LiveIngestionRepository(db),
                ).__dict__
            finally:
                db.close()
        results.append(result)
        print(
            f"tick={tick:03d} generated={len(batch)} accepted={result['accepted']} "
            f"duplicates={result['duplicates']} database_ms={result['database_ms']:.2f} "
            f"total_ms={result['total_ms']:.2f} segments={result['segments']}"
        )

    with engine.connect() as connection:
        diagnostics = {
            "run_rows": connection.execute(text("""
                SELECT count(*) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "latest_timestamp": connection.execute(text("""
                SELECT max(p.timestamp) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "regions": connection.execute(text("""
                SELECT count(DISTINCT p.region_id) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "segments": connection.execute(text("""
                SELECT count(DISTINCT p.segment_id) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "vehicles": connection.execute(text("""
                SELECT count(DISTINCT p.vehicle_id) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "speed_variants": connection.execute(text("""
                SELECT count(*) FROM (
                    SELECT p.vehicle_id FROM gps_pings p
                    JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                    WHERE b.source_id = :source_id AND b.run_id = :run_id
                    GROUP BY p.vehicle_id HAVING count(DISTINCT p.speed_kmph) > 1
                ) changed
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "event_rows": connection.execute(text("""
                SELECT count(*) FROM gps_pings p
                JOIN live_ingestion_batches b ON b.id = p.ingestion_batch_id
                WHERE b.source_id = :source_id AND b.run_id = :run_id AND p.label <> 'normal'
            """), {"source_id": "manual-live-verification", "run_id": args.run_id}).scalar_one(),
            "state_rows": connection.execute(text("SELECT count(*) FROM segment_current_state")).scalar_one(),
        }

    print(f"event_segment={event_segment}")
    print(f"accepted_total={sum(result['accepted'] for result in results)}")
    print(f"average_database_ms={statistics.mean(result['database_ms'] for result in results):.2f}")
    print(f"average_total_ms={statistics.mean(result['total_ms'] for result in results):.2f}")
    for key, value in diagnostics.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
