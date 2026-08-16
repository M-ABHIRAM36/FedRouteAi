"""Batch receipts and the latest derived state for each road segment."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LiveIngestionBatch(Base):
    __tablename__ = "live_ingestion_batches"
    __table_args__ = (
        UniqueConstraint("source_id", "run_id", "batch_id", name="uq_live_batch_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(60), index=True)
    run_id: Mapped[str] = mapped_column(String(80))
    batch_id: Mapped[str] = mapped_column(String(80))
    tick_number: Mapped[int] = mapped_column(Integer)
    payload_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_count: Mapped[int] = mapped_column(Integer)
    segment_count: Mapped[int] = mapped_column(Integer)
    region_count: Mapped[int] = mapped_column(Integer)
    average_speed_kmph: Mapped[float] = mapped_column(Float)


class SegmentCurrentState(Base):
    __tablename__ = "segment_current_state"

    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), primary_key=True)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.region_id"), index=True)
    latest_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    ingestion_batch_id: Mapped[int] = mapped_column(ForeignKey("live_ingestion_batches.id"))
    vehicle_count: Mapped[int] = mapped_column(Integer)
    average_speed_kmph: Mapped[float] = mapped_column(Float)
    density: Mapped[float] = mapped_column(Float)
    current_event: Mapped[str] = mapped_column(String(20), default="normal")
    available: Mapped[bool] = mapped_column(default=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime)
