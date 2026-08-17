from sqlalchemy.orm import Session

from app.models.segment import Segment
from app.repositories.base_repository import BaseRepository
from app.utils.geo_utils import meters_per_deg_lon, METERS_PER_DEG_LAT


class SegmentRepository(BaseRepository[Segment]):
    def __init__(self, db: Session):
        super().__init__(db, Segment)

    def get_by_region(self, region_id: str) -> list[Segment]:
        return self.db.query(Segment).filter(Segment.region_id == region_id).all()

    def get_many(self, segment_ids: set[str]) -> dict[str, Segment]:
        if not segment_ids:
            return {}
        rows = self.db.query(Segment).filter(Segment.segment_id.in_(segment_ids)).all()
        return {row.segment_id: row for row in rows}

    def get_neighbors(self, segment: Segment) -> list[Segment]:
        ids = [s for s in (segment.neighbor_segments or "").split(";") if s]
        if not ids:
            return []
        return self.db.query(Segment).filter(Segment.segment_id.in_(ids)).all()

    def get_candidates_near(self, lat: float, lon: float, radius_m: float = 60.0) -> list[Segment]:
        """Cheap bounding-box prefilter (not a true radius, but tight
        enough to keep the matcher from scanning the whole table on
        every ping). A real deployment should replace this with a
        PostGIS `ST_DWithin` query once segments have a geometry column
        instead of plain lat/lon floats — see docs/architecture.md."""
        dlat = radius_m / METERS_PER_DEG_LAT
        dlon = radius_m / meters_per_deg_lon(lat)
        return (
            self.db.query(Segment)
            .filter(
                Segment.start_lat.between(lat - dlat, lat + dlat) | Segment.end_lat.between(lat - dlat, lat + dlat),
                Segment.start_lon.between(lon - dlon, lon + dlon) | Segment.end_lon.between(lon - dlon, lon + dlon),
            )
            .all()
        )
