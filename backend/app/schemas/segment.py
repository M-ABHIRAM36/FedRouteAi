"""Request/response shapes for the segments API. Kept separate from
app/models (the DB layer) on purpose — the API contract should be free
to diverge from the storage schema (e.g. hiding internal columns,
renaming fields for the frontend) without touching the DB model."""
from pydantic import BaseModel, ConfigDict, Field


class LineStringGeometry(BaseModel):
    type: str = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    segment_id: str
    road_name: str
    road_type: str
    region_id: str
    pincode: int
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    segment_length_m: float
    number_of_lanes: int
    road_width_m: float
    max_speed_kmph: float
    road_direction: str
    flood_prone: bool
    neighbor_segments: list[str] = []
    geometry: LineStringGeometry | None = None
    network_source: str | None = None
    network_version: str | None = None
    osm_way_id: int | None = None

    # @classmethod
    # def from_orm_row(cls, row) -> "SegmentOut":
    #     obj = cls.model_validate(row)
    #     obj.neighbor_segments = [s for s in (row.neighbor_segments or "").split(";") if s]
    #     return obj
    @classmethod
    def from_orm_row(cls, row, metadata=None, coordinates=None) -> "SegmentOut":
        return cls(
            segment_id=row.segment_id,
            road_name=row.road_name,
            road_type=row.road_type,
            region_id=row.region_id,
            pincode=row.pincode,
            start_lat=row.start_lat,
            start_lon=row.start_lon,
            end_lat=row.end_lat,
            end_lon=row.end_lon,
            segment_length_m=row.segment_length_m,
            number_of_lanes=row.number_of_lanes,
            road_width_m=row.road_width_m,
            max_speed_kmph=row.max_speed_kmph,
            road_direction=row.road_direction,
            flood_prone=row.flood_prone,
            neighbor_segments=[
                s for s in (row.neighbor_segments or "").split(";") if s
            ],
            geometry=LineStringGeometry(coordinates=coordinates) if coordinates else None,
            network_source=metadata.network_source if metadata else None,
            network_version=metadata.network_version if metadata else None,
            osm_way_id=metadata.osm_way_id if metadata else None,
        )
