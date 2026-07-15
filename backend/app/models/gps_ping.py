"""One raw (map-matched) GPS observation. High write volume — this table
is the one you'll want to partition by timestamp once it's real traffic
instead of the synthetic dataset.

NOTE: `id` is Integer, not BigInteger, on purpose — SQLite only grants
its fast implicit-rowid autoincrement to columns typed exactly INTEGER
(this project's test suite runs against SQLite; production runs
Postgres). Integer caps at ~2.1 billion rows, which is enormous for
this table's cadence but not infinite — if you ever approach that on
Postgres, a targeted migration to BIGSERIAL there is a one-column
change; it doesn't ripple anywhere else in the codebase."""
from datetime import datetime

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GPSPing(Base):
    __tablename__ = "gps_pings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), index=True)
    region_id: Mapped[str] = mapped_column(String(20), index=True)
    vehicle_id: Mapped[str] = mapped_column(String(60))
    vehicle_type: Mapped[str] = mapped_column(String(10))

    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    speed_kmph: Mapped[float] = mapped_column(Float)
    heading_deg: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)

    is_uturn_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    # ground-truth label, only populated for synthetic/training data —
    # real ingested traffic won't have this, that's what the model predicts
    label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
