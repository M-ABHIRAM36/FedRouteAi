"""The fundamental unit of the whole system: the road between two
neighboring intersections. Mirrors the schema in the project spec and
the synthetic dataset 1:1 — swap in a real OSMnx pull and nothing
downstream needs to change."""
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Segment(Base):
    __tablename__ = "segments"

    segment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    road_name: Mapped[str] = mapped_column(String(120))
    road_type: Mapped[str] = mapped_column(String(20))  # see core.constants.RoadType
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.region_id"), index=True)
    pincode: Mapped[int] = mapped_column(Integer)

    start_lat: Mapped[float] = mapped_column(Float)
    start_lon: Mapped[float] = mapped_column(Float)
    end_lat: Mapped[float] = mapped_column(Float)
    end_lon: Mapped[float] = mapped_column(Float)

    segment_length_m: Mapped[float] = mapped_column(Float)
    number_of_lanes: Mapped[int] = mapped_column(Integer)
    road_width_m: Mapped[float] = mapped_column(Float)
    max_speed_kmph: Mapped[float] = mapped_column(Float)
    road_direction: Mapped[str] = mapped_column(String(20))  # see core.constants.RoadDirection
    flood_prone: Mapped[bool] = mapped_column(Boolean, default=False)

    # semicolon-separated segment_ids — kept denormalized for O(1) reads;
    # the graph_builder service is the source of truth and can rebuild this
    neighbor_segments: Mapped[str] = mapped_column(String(1000), default="")
