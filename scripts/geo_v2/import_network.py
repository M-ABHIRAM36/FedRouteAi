"""Import the cached Beeramguda OSM network as an additive Geo V2 version."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.geo_v2_repository import GeoV2Repository  # noqa: E402
from app.services.geo_v2.network import load_overpass_json  # noqa: E402
from scripts.geo_v2.common import NETWORK_SOURCE, NETWORK_VERSION  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/geo_v2/beeramguda_roads.osm.json")
    parser.add_argument("--version", default=NETWORK_VERSION)
    args = parser.parse_args()
    network = load_overpass_json(args.input)
    db = SessionLocal()
    try:
        GeoV2Repository(db).replace_network(
            network,
            network_version=args.version,
            network_source=NETWORK_SOURCE,
            imported_at=datetime.now(UTC).replace(tzinfo=None),
        )
    finally:
        db.close()
    print(f"imported {len(network.segments)} segments and {len(network.transitions)} transitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
