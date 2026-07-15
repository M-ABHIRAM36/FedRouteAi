"""Per-segment, per-hour-of-day baseline behavior — the 'normal road
memory' every anomaly gets compared against. Computed by
services/historical_memory/aggregator.py, never written by hand."""
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HistoricalMemory(Base):
    __tablename__ = "segment_historical_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment_id: Mapped[str] = mapped_column(String(30), index=True)
    hour_of_day: Mapped[int] = mapped_column(Integer)  # 0-23

    avg_speed_kmph: Mapped[float] = mapped_column(Float)
    std_speed_kmph: Mapped[float] = mapped_column(Float)
    avg_vehicle_count: Mapped[float] = mapped_column(Float)
    uturn_rate: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
