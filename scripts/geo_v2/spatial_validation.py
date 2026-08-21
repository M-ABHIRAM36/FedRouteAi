"""Write a JSON spatial validation report for Geo V2 simulation telemetry."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.geo_v2.alignment import spatial_alignment_report  # noqa: E402
from app.services.geo_v2.network import load_overpass_json  # noqa: E402
from scripts.geo_v2.common import write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", type=Path, required=True)
    parser.add_argument("--osm", type=Path, default=ROOT / "data/geo_v2/beeramguda_roads.osm.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/geo_v2/spatial_validation.json")
    parser.add_argument("--tolerance-m", type=float, default=1.0)
    args = parser.parse_args()
    network = load_overpass_json(args.osm)
    rows = pd.read_csv(args.telemetry).to_dict("records")
    report = spatial_alignment_report(rows, network, valid_tolerance_m=args.tolerance_m)
    write_json(args.output, {**asdict(report), "tolerance_m": args.tolerance_m, "network_segments": len(network.segments)})
    print(f"valid={report.valid}/{report.total} p95_m={report.p95_m:.3f} max_m={report.max_m:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
