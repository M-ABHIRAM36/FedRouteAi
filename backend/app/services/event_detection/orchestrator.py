"""
Event Detection Orchestrator
--------------------------------
The piece that makes the individually-tested services (signature
extraction, pattern matching, graph reasoning) actually run together
against real data. This is what ingest.py calls (as a background task)
after persisting new pings for a segment.

Flow:
  1. Pull this segment's historical baseline for the current hour.
     No baseline yet -> nothing to compare against -> bail out quietly
     (this is expected/normal during a cold start, not an error).
  2. Pull recent pings for the segment -> extract_signature().
  3. match_event() against the Event Memory patterns.
  4. If significant: pull the segment's neighbors' signatures too (same
     extraction, cheap since they're already ingested), run
     neighbor_reasoning to adjust confidence, then write an Event row
     if still above threshold after that adjustment.
"""
from datetime import datetime, timedelta

from app.utils.time_utils import utcnow

from sqlalchemy.orm import Session

from app.models.event import Event
from app.repositories.segment_repository import SegmentRepository
from app.repositories.gps_repository import GPSPingRepository
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.event_repository import EventRepository
from app.services.event_detection.signature_extractor import extract_signature
from app.services.event_detection.pattern_matcher import match_event
from app.services.road_graph.graph_builder import build_segment_graph
from app.services.road_graph.neighbor_reasoning import reason_over_neighbors
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

SIGNATURE_WINDOW_MINUTES = 20  # how far back "recent" pings go for signature extraction


def _next_event_id(db: Session) -> str:
    count = db.query(Event).count()
    return f"EVT_{count + 1:04d}"


def detect_and_record_event(db: Session, segment_id: str, as_of: datetime | None = None) -> Event | None:
    as_of = as_of or utcnow()
    hour = as_of.hour

    segment_repo = SegmentRepository(db)
    gps_repo = GPSPingRepository(db)
    memory_repo = HistoricalMemoryRepository(db)
    event_repo = EventRepository(db)

    segment = segment_repo.get(segment_id)
    if segment is None:
        logger.warning("detect_and_record_event: unknown segment_id=%s", segment_id)
        return None

    baseline = memory_repo.get_baseline(segment_id, hour)
    if baseline is None:
        logger.debug("No baseline yet for %s @ hour %d — skipping detection (cold start)", segment_id, hour)
        return None

    since = as_of - timedelta(minutes=SIGNATURE_WINDOW_MINUTES)
    recent_pings = gps_repo.get_recent_for_segment(segment_id, since)
    signature = extract_signature(recent_pings, baseline, window_minutes=SIGNATURE_WINDOW_MINUTES)
    if signature is None:
        return None

    matched = match_event(signature)
    if not matched.is_significant:
        return None

    # --- graph reasoning: does the neighborhood corroborate this? ---
    all_segments = segment_repo.list_all(limit=100_000)
    graph = build_segment_graph(all_segments)
    neighbor_ids = [s for s in (segment.neighbor_segments or "").split(";") if s]

    neighbor_deviation_lookup: dict[str, float] = {}
    for n_id in neighbor_ids:
        n_baseline = memory_repo.get_baseline(n_id, hour)
        n_recent = gps_repo.get_recent_for_segment(n_id, since)
        if n_baseline is None or not n_recent:
            continue
        n_sig = extract_signature(n_recent, n_baseline, window_minutes=SIGNATURE_WINDOW_MINUTES)
        if n_sig is None:
            continue
        # cheap deviation score reused for neighbor reasoning's threshold check
        deviation = abs(n_sig.speed_ratio - 1) + abs(n_sig.density_ratio - 1) + abs(n_sig.uturn_ratio - 1)
        neighbor_deviation_lookup[n_id] = deviation

    reasoning = reason_over_neighbors(graph, segment_id, neighbor_deviation_lookup)
    final_confidence = max(0.0, min(1.0, matched.confidence + reasoning.confidence_delta))

    if final_confidence < settings.EVENT_CONFIDENCE_THRESHOLD:
        logger.debug("%s: confidence dropped below threshold after graph reasoning (%.3f)", segment_id, final_confidence)
        return None

    event = Event(
        event_id=_next_event_id(db),
        event_type=matched.event_type,
        region_id=segment.region_id,
        primary_segment_id=segment_id,
        start_time=as_of,
        end_time=as_of,  # updated by a future "close out" pass once the event stops recurring
        duration_hours=0,
        confidence=round(final_confidence, 3),
        severity=round(final_confidence, 3),  # proxy until a dedicated severity signal exists
        affected_neighbors=";".join(reasoning.supporting_neighbors or neighbor_ids),
        source="detected",
    )
    event_repo.add(event)
    logger.info("Recorded event %s: %s on %s (confidence=%.3f)", event.event_id, event.event_type, segment_id, final_confidence)
    return event
