"""
GPS ingestion endpoint — fully wired: map-match each ping in the batch,
persist it, then kick off event detection in the background for every
segment that received new pings.

Detection runs as a FastAPI BackgroundTask (in-process, after the
response is sent) rather than a queue/broker — deliberate for Phase 1
per the "avoid deployment complexity for now" scope. It's a real
functional boundary already (this function doesn't block detection
logic, and swapping BackgroundTasks for a Celery/RQ task later is a
small, localized change), just not horizontally scalable yet.
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.gps_ping import GPSPing
from app.repositories.segment_repository import SegmentRepository
from app.repositories.gps_repository import GPSPingRepository
from app.schemas.gps_ping import GPSBatchIn
from app.services.map_matching.matcher import match_trajectory
from app.services.event_detection.orchestrator import detect_and_record_event
from app.core.logging_config import get_logger

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = get_logger(__name__)


def _run_detection_for_segments(segment_ids: set[str], db_factory) -> None:
    """Background task body. Opens its OWN db session — the request's
    session is closed by the time this runs, since it executes after
    the response is returned."""
    db = db_factory()
    try:
        for segment_id in segment_ids:
            try:
                detect_and_record_event(db, segment_id)
            except Exception:
                logger.exception("Detection failed for segment %s", segment_id)
    finally:
        db.close()


@router.post("/gps", status_code=status.HTTP_202_ACCEPTED)
def ingest_gps_batch(batch: GPSBatchIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not batch.pings:
        return {"accepted": 0, "matched": 0, "device_id": batch.device_id}

    segment_repo = SegmentRepository(db)

    # spatially prefilter candidates once per batch using the batch's
    # rough centroid — good enough since one batch is one short trip,
    # not a cross-city trajectory. See matcher.py for per-point matching.
    avg_lat = sum(p.lat for p in batch.pings) / len(batch.pings)
    avg_lon = sum(p.lon for p in batch.pings) / len(batch.pings)
    candidates = segment_repo.get_candidates_near(avg_lat, avg_lon, radius_m=150.0)

    points = [(p.lat, p.lon) for p in batch.pings]
    match_results = match_trajectory(points, candidates)

    new_pings: list[GPSPing] = []
    touched_segments: set[str] = set()

    for raw, matched in zip(batch.pings, match_results):
        if matched.segment_id is None:
            continue  # unmatched pings are dropped, not stored with a null FK
        new_pings.append(GPSPing(
            segment_id=matched.segment_id,
            region_id=next((c.region_id for c in candidates if c.segment_id == matched.segment_id), ""),
            vehicle_id=batch.device_id,
            vehicle_type="unknown",
            lat=raw.lat, lon=raw.lon,
            speed_kmph=raw.speed_kmph or 0.0,
            heading_deg=raw.heading_deg or 0.0,
            timestamp=raw.timestamp,
            is_uturn_flag=False,  # TODO: derive from consecutive heading deltas in the batch
            label=None,           # real ingested data has no ground-truth label
            event_id=None,
        ))
        touched_segments.add(matched.segment_id)

    GPSPingRepository(db).bulk_insert(new_pings)

    if touched_segments:
        from app.db.session import SessionLocal
        background_tasks.add_task(_run_detection_for_segments, touched_segments, SessionLocal)

    return {
        "accepted": len(batch.pings),
        "matched": len(new_pings),
        "unmatched": len(batch.pings) - len(new_pings),
        "device_id": batch.device_id,
        "segments_queued_for_detection": list(touched_segments),
    }
