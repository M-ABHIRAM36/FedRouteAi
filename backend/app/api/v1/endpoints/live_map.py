from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.live_map_repository import LiveMapRepository
from app.schemas.live_map import LiveMapSnapshotOut
from app.services.live_map.service import LiveMapNotFoundError, build_live_map_snapshot


router = APIRouter(prefix="/live-map", tags=["live-map"])


@router.get("/snapshot", response_model=LiveMapSnapshotOut)
def get_live_map_snapshot(
    source_id: str | None = Query(default=None, max_length=60),
    run_id: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    try:
        return build_live_map_snapshot(LiveMapRepository(db), source_id, run_id)
    except LiveMapNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
