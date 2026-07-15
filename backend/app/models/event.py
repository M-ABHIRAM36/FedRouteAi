"""A detected (or, for synthetic data, injected ground-truth) road event.
This is the row that ultimately becomes the JSON object the system
outputs to navigation providers / traffic management systems."""
from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20))  # see core.constants.EventType
    region_id: Mapped[str] = mapped_column(String(20), index=True)
    primary_segment_id: Mapped[str] = mapped_column(String(30), index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    duration_hours: Mapped[int] = mapped_column(Integer)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[float] = mapped_column(Float, default=0.0)

    # semicolon-separated segment_ids that showed a secondary/spillover effect
    affected_neighbors: Mapped[str] = mapped_column(String(500), default="")

    # "detected" (produced by the live pipeline) vs "ground_truth" (synthetic/injected)
    source: Mapped[str] = mapped_column(String(20), default="detected")
