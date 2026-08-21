"""Verification-only runner for isolated Geo V2 live scenario smoke tests."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.geo_v2 import SegmentPrediction  # noqa: E402
from app.models.gps_ping import GPSPing  # noqa: E402
from app.models.live_ingestion import LiveIngestionBatch  # noqa: E402


SCENARIOS = {
    "NORMAL": [],
    "CONGESTION": ["congestion"],
    "ACCIDENT": ["accident"],
    "CONSTRUCTION": ["construction"],
    "FLOOD": ["flood"],
    "DIVERSION": ["diversion"],
    "ROAD_DAMAGE": ["road_damage"],
    "ROAD_BLOCK": ["road_block"],
    "ACCIDENT+CONGESTION": ["accident", "congestion"],
    "ROAD_BLOCK+CONGESTION": ["road_block", "congestion"],
    "FLOOD+CONGESTION": ["flood", "congestion"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--target-segment", required=True)
    parser.add_argument("--start", default="2026-08-17T08:00:00")
    parser.add_argument("--only", help="comma-separated scenario names")
    parser.add_argument("--run-prefix", default="scenario")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start)
    selected = set(args.only.split(",")) if args.only else set(SCENARIOS)
    results = []
    for index, (name, event_types) in enumerate(SCENARIOS.items(), 1):
        if name not in selected:
            continue
        source_id = "geo-v2-final-scenarios"
        run_id = f"{args.run_prefix}-{index:02d}-{name.lower().replace('+', '-').replace('_', '-')}"
        if event_types:
            response = httpx.post(
                f"{args.base_url}/api/v1/live-scenarios",
                json={
                    "source_id": source_id,
                    "run_id": run_id,
                    "scenarios": [{
                        "type": event_type, "segment_id": args.target_segment,
                        "severity": 0.85, "duration_seconds": 600, "start_time": start.isoformat(),
                    } for event_type in event_types],
                },
                timeout=30,
            )
            response.raise_for_status()
        command = [
            sys.executable, str(ROOT / "scripts/geo_v2/live_demo.py"),
            "--base-url", args.base_url, "--api-key", settings.LIVE_INGEST_API_KEY,
            "--source-id", source_id, "--run-id", run_id, "--ticks", "1",
            "--vehicle-count", "1000", "--tick-seconds", "120", "--start", args.start,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180, check=True)
        db = SessionLocal()
        try:
            batch = db.query(LiveIngestionBatch).filter_by(source_id=source_id, run_id=run_id).one()
            predictions = db.query(SegmentPrediction).filter_by(source_id=source_id, run_id=run_id).all()
            observations = db.query(GPSPing).filter_by(ingestion_batch_id=batch.id).all()
            target = next((row for row in predictions if row.segment_id == args.target_segment), None)
            results.append({
                "scenario": name,
                "ground_truth": event_types,
                "observed_segment": args.target_segment if target else None,
                "prediction": target.predicted_label if target else None,
                "probabilities": target.class_probabilities if target else None,
                "model_version": target.model_version if target else None,
                "feature_version": target.historical_baseline.get("feature_version") if target else None,
                "observations": len(observations),
                "observed_segments": batch.segment_count,
                "predictions": len(predictions),
                "prediction_distribution": dict(Counter(row.predicted_label for row in predictions)),
                "leaked_labels": sum(row.label != "normal" for row in observations),
                "leaked_event_ids": sum(bool(row.event_id) for row in observations),
                "timing": completed.stdout.strip(),
            })
        finally:
            db.close()
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
