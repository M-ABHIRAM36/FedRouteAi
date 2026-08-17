from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.segment_repository import SegmentRepository
from app.repositories.geo_v2_repository import GeoV2Repository
from app.schemas.segment import SegmentOut

router = APIRouter(prefix="/segments", tags=["segments"])


@router.get("", response_model=list[SegmentOut])
def list_segments(
    region_id: str | None = None,
    network_source: str | None = None,
    db: Session = Depends(get_db),
):
    if network_source:
        repository = GeoV2Repository(db)
        rows = repository.list_segments(network_source)
        if region_id:
            rows = [row for row in rows if row[0].region_id == region_id]
        return [
            SegmentOut.from_orm_row(segment, metadata, repository.geometry_coordinates(metadata))
            for segment, metadata in rows
        ]
    repo = SegmentRepository(db)
    rows = repo.get_by_region(region_id) if region_id else repo.list_all(limit=500)
    return [SegmentOut.from_orm_row(r) for r in rows]


@router.get("/{segment_id}", response_model=SegmentOut)
def get_segment(segment_id: str, db: Session = Depends(get_db)):
    repo = SegmentRepository(db)
    row = repo.get(segment_id)
    if not row:
        raise HTTPException(status_code=404, detail="segment not found")
    return SegmentOut.from_orm_row(row)


@router.get("/{segment_id}/neighbors", response_model=list[SegmentOut])
def get_segment_neighbors(segment_id: str, db: Session = Depends(get_db)):
    repo = SegmentRepository(db)
    row = repo.get(segment_id)
    if not row:
        raise HTTPException(status_code=404, detail="segment not found")
    return [SegmentOut.from_orm_row(n) for n in repo.get_neighbors(row)]
