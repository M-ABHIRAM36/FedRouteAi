"""Tracks each region's contribution per FL round — this is what lets
adaptive_aggregation.py compute historical_similarity and
temporal_recency for real instead of treating every round as identical."""
from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FLRoundRecord(Base):
    __tablename__ = "fl_round_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[str] = mapped_column(String(20), index=True)
    round_number: Mapped[int] = mapped_column(Integer, index=True)

    data_quality_score: Mapped[float] = mapped_column(Float)
    local_loss: Mapped[float] = mapped_column(Float)
    num_samples: Mapped[int] = mapped_column(Integer)

    # mean feature vector this round, comma-separated floats — used to
    # compute historical_similarity against this SAME region's own
    # previous round (consistency), not against other regions
    mean_vector_csv: Mapped[str] = mapped_column(String(200))

    data_timestamp: Mapped[datetime] = mapped_column(DateTime)  # freshness of the training data itself
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
