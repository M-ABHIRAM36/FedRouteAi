"""
Datasource Abstraction
-----------------------
Decouples the feature pipeline from where data comes from. Today it reads
CSV files (fast, no DB needed for offline training). Tomorrow a DatabaseSource
implementation lets the pipeline pull straight from the live PostgreSQL DB —
enabling continuous retraining without re-exporting CSVs.

Usage:
    # Offline training from generated dataset
    source = CSVSource(
        gps_path="data/raw/fedrouteai_dataset/global/gps_pings_all.csv",
        segments_path="data/raw/fedrouteai_dataset/road_network/segments.csv",
        memory_path="data/raw/fedrouteai_dataset/global/segment_historical_memory.csv",
    )

    # Live retraining from the Postgres DB
    source = DatabaseSource(db_url=settings.DATABASE_URL)

    # Both expose the same interface — the pipeline code doesn't know the difference.
    gps_df, segments_df, memory_df = source.load()
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class FeatureSource(ABC):
    """Abstract base: anything that can supply the three raw DataFrames needed
    by the feature pipeline."""

    @abstractmethod
    def load(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Return (gps_df, segments_df, memory_df).

        gps_df columns (required):
            segment_id, region_id, vehicle_id, speed_kmph, timestamp,
            is_uturn_flag, label

        segments_df columns (required):
            segment_id, region_id, road_type, number_of_lanes,
            flood_prone, neighbor_segments

        memory_df columns (required):
            segment_id, hour_of_day, avg_speed_kmph, std_speed_kmph,
            avg_vehicle_count, uturn_rate
        """

    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this source, for logging."""


class CSVSource(FeatureSource):
    """Loads from the CSV files written by scripts/dataset_generator/generate_dataset.py."""

    # Columns we actually need — avoids loading unnecessary bytes from the 62MB CSV
    _GPS_COLS = ["segment_id", "region_id", "vehicle_id", "speed_kmph",
                 "timestamp", "is_uturn_flag", "label"]
    _SEG_COLS = ["segment_id", "region_id", "road_type", "number_of_lanes",
                 "flood_prone", "neighbor_segments"]
    # Use a callable for memory columns to gracefully handle V1 vs V2 formats
    _MEM_COLS_SET = {"segment_id", "hour_of_day", "day_type", "avg_speed_kmph",
                     "std_speed_kmph", "avg_vehicle_count", "avg_vehicle_count_per_20min",
                     "uturn_rate"}

    def __init__(
        self,
        gps_path: str | Path,
        segments_path: str | Path,
        memory_path: str | Path,
    ) -> None:
        self.gps_path = Path(gps_path)
        self.segments_path = Path(segments_path)
        self.memory_path = Path(memory_path)

        for p in (self.gps_path, self.segments_path, self.memory_path):
            if not p.exists():
                raise FileNotFoundError(
                    f"CSVSource: required file not found: {p}\n"
                    "Run scripts/generate_dataset_then_seed.sh first."
                )

    def load(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        gps_df = pd.read_csv(
            self.gps_path,
            usecols=self._GPS_COLS,
            parse_dates=["timestamp"],
        )
        segments_df = pd.read_csv(self.segments_path, usecols=self._SEG_COLS)
        memory_df = pd.read_csv(self.memory_path, usecols=lambda c: c in self._MEM_COLS_SET)
        return gps_df, segments_df, memory_df

    def description(self) -> str:
        return f"CSVSource(gps={self.gps_path.name}, segs={self.segments_path.name})"


class DatabaseSource(FeatureSource):
    """Loads from the live PostgreSQL database via SQLAlchemy.

    Pulls only the columns needed — avoids loading geometry columns, etc.
    Requires a running database with seeded data.
    """

    _GPS_QUERY = """
        SELECT segment_id, region_id, vehicle_id, speed_kmph,
               timestamp, is_uturn_flag, label
        FROM gps_pings
        WHERE label IS NOT NULL
    """
    _SEG_QUERY = """
        SELECT segment_id, region_id, road_type, number_of_lanes,
               flood_prone, neighbor_segments
        FROM segments
    """
    _MEM_QUERY = """
        SELECT *
        FROM segment_historical_memory
    """

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def load(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        from sqlalchemy import create_engine, text  # lazy import — only needed at runtime
        engine = create_engine(self.db_url)
        with engine.connect() as conn:
            gps_df = pd.read_sql(text(self._GPS_QUERY), conn, parse_dates=["timestamp"])
            segments_df = pd.read_sql(text(self._SEG_QUERY), conn)
            memory_df = pd.read_sql(text(self._MEM_QUERY), conn)
        return gps_df, segments_df, memory_df

    def description(self) -> str:
        # Hide credentials in logs
        safe = self.db_url.split("@")[-1] if "@" in self.db_url else self.db_url
        return f"DatabaseSource(db={safe})"
