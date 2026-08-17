"""Audit a generated Geo V2 ML v1 dataset and abort on violations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.ml.geo_v2.audit import audit_dataset  # noqa: E402
from app.services.geo_v2.network import load_overpass_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1")
    parser.add_argument("--osm", type=Path, default=ROOT / "data/geo_v2/beeramguda_roads.osm.json")
    args = parser.parse_args()
    report = audit_dataset(args.dataset, load_overpass_json(args.osm))
    print(json.dumps({"status": report["status"], "features": {name: value["rows"] for name, value in report["features"].items()}, "gps": report["gps"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
