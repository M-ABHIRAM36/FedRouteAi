"""Trusted pre-matched live simulator ingestion and current-state reads."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.repositories.live_ingestion_repository import LiveIngestionRepository
from app.schemas.gps_ping import LiveGPSBatchIn, LiveGPSBatchResult
from app.services.live_ingestion.service import (
    LiveBatchConflictError,
    LiveBatchValidationError,
    ingest_live_batch,
)

router = APIRouter(prefix="/ingest/live", tags=["live-ingest"])


def _check_api_key(api_key: str | None) -> None:
    if not settings.LIVE_INGEST_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live ingestion is disabled until LIVE_INGEST_API_KEY is configured",
        )
    if api_key != settings.LIVE_INGEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid live ingestion API key")


@router.post("/batch", response_model=LiveGPSBatchResult)
def ingest_live_batch_endpoint(
    batch: LiveGPSBatchIn,
    db: Session = Depends(get_db),
    x_live_ingest_key: str | None = Header(default=None),
):
    _check_api_key(x_live_ingest_key)
    if len(batch.observations) > settings.LIVE_INGEST_MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"batch exceeds {settings.LIVE_INGEST_MAX_BATCH_SIZE} observations",
        )
    try:
        return ingest_live_batch(batch, LiveIngestionRepository(db))
    except LiveBatchConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except LiveBatchValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        # A concurrent retry may have won the unique batch race. Return its
        # result only after confirming that the payload is identical.
        existing = LiveIngestionRepository(db).get_batch(batch.source_id, batch.run_id, batch.batch_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="batch was submitted concurrently; retry with the same batch identity",
            ) from error
        raise HTTPException(status_code=500, detail="live batch persistence failed") from error


@router.get("/current-state")
def get_live_current_state(
    segment_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    states = LiveIngestionRepository(db).current_states({segment_id} if segment_id else None)
    return [
        {
            "segment_id": state.segment_id,
            "region_id": state.region_id,
            "latest_timestamp": state.latest_timestamp,
            "vehicle_count": state.vehicle_count,
            "average_speed_kmph": state.average_speed_kmph,
            "density": state.density,
            "current_event": state.current_event,
            "available": state.available,
            "last_updated": state.last_updated,
        }
        for state in states
    ]
