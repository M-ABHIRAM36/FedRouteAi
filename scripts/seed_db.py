"""
Loads the synthetic dataset (from scripts/dataset_generator/) into the
database via the real ORM models — this is the bridge between "we have
CSVs" and "the API/services can actually query this."

Usage:
    python scripts/generate_dataset_then_seed.sh   (recommended, does both steps)
  or, if data/raw/fedrouteai_dataset already exists:
    PYTHONPATH=backend python scripts/seed_db.py
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.models.region import Region
from app.models.segment import Segment
from app.models.event import Event
from app.models.historical_memory import HistoricalMemory
from app.core.logging_config import get_logger

logger = get_logger(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "fedrouteai_dataset")


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def seed():
    init_db()
    db = SessionLocal()
    try:
        regions_csv = _read_csv(os.path.join(DATA_DIR, "road_network", "regions.csv"))
        db.add_all([
            Region(region_id=r["region_id"], pincode=int(r["pincode"]),
                   center_lat=float(r["center_lat"]), center_lon=float(r["center_lon"]),
                   segment_count=int(r["segment_count"]))
            for r in regions_csv
        ])
        db.commit()
        logger.info("Seeded %d regions", len(regions_csv))

        segments_csv = _read_csv(os.path.join(DATA_DIR, "road_network", "segments.csv"))
        db.add_all([
            Segment(
                segment_id=s["segment_id"], road_name=s["road_name"], road_type=s["road_type"],
                region_id=s["region_id"], pincode=int(s["pincode"]),
                start_lat=float(s["start_lat"]), start_lon=float(s["start_lon"]),
                end_lat=float(s["end_lat"]), end_lon=float(s["end_lon"]),
                segment_length_m=float(s["segment_length_m"]), number_of_lanes=int(s["number_of_lanes"]),
                road_width_m=float(s["road_width_m"]), max_speed_kmph=float(s["max_speed_kmph"]),
                road_direction=s["road_direction"], flood_prone=s["flood_prone"] == "True",
                neighbor_segments=s["neighbor_segments"],
            )
            for s in segments_csv
        ])
        db.commit()
        logger.info("Seeded %d segments", len(segments_csv))

        memory_csv = _read_csv(os.path.join(DATA_DIR, "global", "segment_historical_memory.csv"))
        db.add_all([
            HistoricalMemory(
                segment_id=m["segment_id"], hour_of_day=int(m["hour_of_day"]),
                avg_speed_kmph=float(m["avg_speed_kmph"]), std_speed_kmph=float(m["std_speed_kmph"]),
                avg_vehicle_count=float(m["avg_vehicle_count"]), uturn_rate=float(m["uturn_rate"]),
                sample_size=int(m["sample_size"]),
            )
            for m in memory_csv
        ])
        db.commit()
        logger.info("Seeded %d historical memory rows", len(memory_csv))

        events_csv = _read_csv(os.path.join(DATA_DIR, "global", "event_log.csv"))
        db.add_all([
            Event(
                event_id=e["event_id"], event_type=e["event_type"], region_id=e["region_id"],
                primary_segment_id=e["primary_segment_id"],
                start_time=datetime.fromisoformat(e["start_time"]),
                end_time=datetime.fromisoformat(e["end_time"]),
                duration_hours=int(e["duration_hours"]), severity=float(e["severity"]),
                confidence=1.0,  # ground truth, not a live detection
                affected_neighbors=e["affected_neighbors"], source="ground_truth",
            )
            for e in events_csv
        ])
        db.commit()
        logger.info("Seeded %d ground-truth events", len(events_csv))

        # NOTE: gps_pings.csv (global/gps_pings_all.csv, ~490K rows) is
        # intentionally NOT bulk-inserted via the ORM here — for
        # anything past a few thousand rows, use `COPY` (psql \copy or
        # psycopg's copy_expert) instead of row-by-row ORM inserts, or
        # this will be extremely slow. See the TODO at the bottom of
        # this file.
        logger.info("Done. (gps_pings NOT loaded — see TODO at bottom of seed_db.py)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

# TODO: bulk-load global/gps_pings_all.csv with Postgres COPY, e.g.:
#   psql $DATABASE_URL -c "\copy gps_pings(segment_id,region_id,vehicle_id,vehicle_type,lat,lon,speed_kmph,heading_deg,timestamp,is_uturn_flag,label,event_id) FROM 'data/raw/fedrouteai_dataset/global/gps_pings_all.csv' CSV HEADER"
# This will be dramatically faster than SQLAlchemy ORM inserts at this volume.
