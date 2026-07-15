"""
Historical Memory Builder (batch job)
----------------------------------------
Orchestrates: fetch a segment's recent pings for one hour-of-day bucket
-> aggregate into a baseline (aggregator.build_hourly_profile) -> upsert
into the historical_memory table. This is the piece that turns
"aggregator.py has a pure function" into "the DB actually gets updated."

Deliberately excludes pings that fall inside a KNOWN event window for
that segment (via EventRepository) — otherwise an ongoing construction
event would slowly get absorbed into the "normal" baseline the longer
it lasts, which defeats the point of having a baseline at all.

Run standalone (`python -m app.services.historical_memory.builder`) as
a periodic job (cron / scheduled task) once this is running against
live data — for Phase 1 it's also fine to call on demand.
"""
from sqlalchemy.orm import Session

from app.repositories.segment_repository import SegmentRepository
from app.repositories.gps_repository import GPSPingRepository
from app.repositories.event_repository import EventRepository
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.services.historical_memory.aggregator import build_hourly_profile
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _excluding_known_events(pings, segment_id: str, hour_of_day: int, event_repo: EventRepository):
    active_events = event_repo.get_active_for_segment(segment_id)
    if not active_events:
        return pings
    return [
        p for p in pings
        if not any(ev.start_time <= p.timestamp <= ev.end_time for ev in active_events)
    ]


def build_memory_for_segment(db: Session, segment_id: str, hour_of_day: int, lookback_days: int = 14) -> bool:
    """Returns True if a baseline was written, False if there wasn't
    enough clean (non-event) data to build one yet."""
    gps_repo = GPSPingRepository(db)
    event_repo = EventRepository(db)
    memory_repo = HistoricalMemoryRepository(db)

    pings = gps_repo.get_for_segment_hour_window(segment_id, hour_of_day, lookback_days)
    clean_pings = _excluding_known_events(pings, segment_id, hour_of_day, event_repo)

    profile = build_hourly_profile(segment_id, hour_of_day, clean_pings)
    if profile is None:
        logger.debug("Not enough clean data for %s @ hour %d yet", segment_id, hour_of_day)
        return False

    memory_repo.upsert(profile)
    return True


def build_memory_for_all_segments(db: Session, lookback_days: int = 14) -> dict:
    """Rebuilds the baseline for every (segment, hour) combination.
    Returns a small summary dict for logging/monitoring — this can run
    long on a real dataset, so callers should run it as a background
    job, not inline in a request."""
    segments = SegmentRepository(db).list_all(limit=100_000)
    written, skipped = 0, 0

    for seg in segments:
        for hour in range(24):
            if build_memory_for_segment(db, seg.segment_id, hour, lookback_days):
                written += 1
            else:
                skipped += 1

    logger.info("Historical memory build complete: %d written, %d skipped (insufficient data)", written, skipped)
    return {"written": written, "skipped": skipped}


if __name__ == "__main__":
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        build_memory_for_all_segments(session)
    finally:
        session.close()
