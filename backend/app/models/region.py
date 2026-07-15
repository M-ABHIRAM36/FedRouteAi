"""A federated-learning silo: a geographic cluster of segments that one
local model / one Flower client owns."""
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    region_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    pincode: Mapped[int] = mapped_column(Integer, nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lon: Mapped[float] = mapped_column(Float, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, default=0)
