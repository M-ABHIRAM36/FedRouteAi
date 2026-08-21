"""Additive Geo V2 network, scenario, and inference persistence."""
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.base import Base


class LineStringStorage(TypeDecorator):
    """PostGIS geometry in production and GeoJSON text in portable tests."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Geometry("LINESTRING", srid=4326, spatial_index=False))
        return dialect.type_descriptor(Text())


class GeoSegmentMetadata(Base):
    __tablename__ = "geo_segment_metadata"
    __table_args__ = (
        UniqueConstraint("network_version", "osm_way_id", "start_node_id", "end_node_id", name="uq_geo_osm_edge"),
    )

    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True)
    network_source: Mapped[str] = mapped_column(String(40), index=True)
    network_version: Mapped[str] = mapped_column(String(80), index=True)
    osm_way_id: Mapped[int] = mapped_column(BigInteger)
    start_node_id: Mapped[int] = mapped_column(BigInteger)
    end_node_id: Mapped[int] = mapped_column(BigInteger)
    highway: Mapped[str] = mapped_column(String(40))
    geometry: Mapped[object] = mapped_column(LineStringStorage())
    bridge: Mapped[bool] = mapped_column(default=False)
    tunnel: Mapped[bool] = mapped_column(default=False)
    junction: Mapped[str | None] = mapped_column(String(40), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class GeoSegmentTransition(Base):
    __tablename__ = "geo_segment_transitions"

    from_segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True)
    to_segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True)
    via_node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    network_version: Mapped[str] = mapped_column(String(80), index=True)


class LiveScenario(Base):
    __tablename__ = "live_scenarios"
    __table_args__ = (Index("ix_live_scenarios_run_time", "run_id", "start_time", "end_time"),)

    event_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(60), index=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    primary_segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"))
    region_id: Mapped[str] = mapped_column(String(20))
    affected_segment_ids: Mapped[list] = mapped_column(JSON)
    severity: Mapped[float] = mapped_column(Float)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    ground_truth_label: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class SegmentPrediction(Base):
    __tablename__ = "segment_predictions"
    __table_args__ = (
        Index("ix_segment_predictions_segment_timestamp", "segment_id", "timestamp"),
        UniqueConstraint("source_id", "run_id", "segment_id", "timestamp", "model_version", name="uq_segment_prediction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(60))
    run_id: Mapped[str] = mapped_column(String(80))
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    predicted_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_probabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String(80))
    historical_baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    current_deviation: Mapped[dict] = mapped_column(JSON, default=dict)
