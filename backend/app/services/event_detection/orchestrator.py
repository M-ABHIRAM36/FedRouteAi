"""
Event Detection Orchestrator
--------------------------------
The piece that makes the individually-tested services (signature
extraction, pattern matching, graph reasoning) actually run together
against real data. This is what ingest.py calls (as a background task)
after persisting new pings for a segment.

Flow (Phase 2 — ML primary + rule-based fallback):
  1. Pull this segment's historical baseline for the current hour.
     No baseline yet → nothing to compare against → bail out quietly
     (expected/normal during cold start, not an error).
  2. Pull recent pings for the segment → extract_signature().
  3. Build the 10-feature vector for ML inference.
  4. [ML PRIMARY] If GlobalModelStore.is_trained:
       → predict(feature_vec) → (event_type, confidence)
       → if confidence ≥ EVENT_CONFIDENCE_THRESHOLD: use this result
  5. [RULE FALLBACK] If ML not trained OR ML confidence too low:
       → match_event() against EVENT_SIGNATURES (existing rule-based path)
       This path is never deleted — it handles:
         a. Cold start (before any FL round completes)
         b. Segments in regions with insufficient training history
         c. Clean ablation study: run with is_trained=False to compare
  6. If significant: pull neighbor signatures, run graph reasoning,
     adjust confidence. Write Event row if still above threshold.

Key: the API contract, routing, graph reasoning, and event schema are
completely unchanged. Only step 4 is new — it's a single function call
that inserts before the existing rule-based path.
"""
from __future__ import annotations

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


def _build_ml_feature_vec(
    sig,           # BehavioralSignature
    segment,       # Segment ORM object
    hour: int,
    neighbor_deviation_lookup: dict[str, float],
) -> "np.ndarray":
    """Build the 10-feature vector for ML inference.
    Matches FEATURE_COLUMNS order in windowing.py exactly.
    Features 8-9 (neighbor_avg_speed, neighbor_density) approximated from
    the neighbor_deviation_lookup already computed for graph reasoning.
    """
    import numpy as np
    from app.ml.features.windowing import ROAD_TYPE_ORDINAL

    # Feature 0-3: ratios from signature (same as training)
    speed_ratio = sig.speed_ratio
    density_ratio = sig.density_ratio
    uturn_ratio = sig.uturn_ratio
    variance_ratio = sig.variance_ratio

    # Feature 4: hour_of_day normalized
    hour_norm = hour / 24.0

    # Feature 5: road_type ordinal
    road_type_enc = ROAD_TYPE_ORDINAL.get(str(getattr(segment, "road_type", "collector")).lower(), 1)

    # Feature 6: lane count
    lane_count = int(getattr(segment, "number_of_lanes", 2))

    # Feature 7: flood_prone
    flood_prone = int(bool(getattr(segment, "flood_prone", False)))

    # Features 8-9: neighbor speed/density proxies from deviation lookup
    # deviation_lookup stores abs(speed-1)+abs(density-1)+abs(uturn-1) —
    # we approximate neighbor_avg_speed as 1 - deviation/3 (bounded 0-1)
    if neighbor_deviation_lookup:
        devs = list(neighbor_deviation_lookup.values())
        avg_dev = sum(devs) / len(devs)
        neighbor_avg_speed = max(0.0, 1.0 - avg_dev / 3.0)
        neighbor_density = min(3.0, 1.0 + avg_dev)
    else:
        neighbor_avg_speed = 0.0
        neighbor_density = 0.0

    return np.array([
        speed_ratio, density_ratio, uturn_ratio, variance_ratio,
        hour_norm, road_type_enc, lane_count, flood_prone,
        neighbor_avg_speed, neighbor_density,
    ], dtype=np.float32)


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
        logger.debug("No baseline yet for %s @ hour %d — skipping (cold start)", segment_id, hour)
        return None

    since = as_of - timedelta(minutes=SIGNATURE_WINDOW_MINUTES)
    recent_pings = gps_repo.get_recent_for_segment(segment_id, since)
    signature = extract_signature(recent_pings, baseline, window_minutes=SIGNATURE_WINDOW_MINUTES)
    if signature is None:
        return None

    # ── graph reasoning: pull neighbor deviations FIRST ──
    # (needed both for graph reasoning AND for building the ML feature vector)
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
        deviation = abs(n_sig.speed_ratio - 1) + abs(n_sig.density_ratio - 1) + abs(n_sig.uturn_ratio - 1)
        neighbor_deviation_lookup[n_id] = deviation

    # ── Step 4: ML PRIMARY classification ──
    from app.services.federated_learning.global_model import GLOBAL_MODEL_STORE

    ml_result = None
    source_path = "rule"

    if GLOBAL_MODEL_STORE.is_trained:
        try:
            feature_vec = _build_ml_feature_vec(signature, segment, hour, neighbor_deviation_lookup)
            ml_event_type, ml_confidence = GLOBAL_MODEL_STORE.predict(feature_vec)
            if ml_confidence >= settings.EVENT_CONFIDENCE_THRESHOLD and ml_event_type != "normal":
                ml_result = (ml_event_type, ml_confidence)
                source_path = "ml"
                logger.debug(
                    "%s: ML classified as %s (confidence=%.3f)",
                    segment_id, ml_event_type, ml_confidence,
                )
        except Exception as exc:
            logger.warning("ML prediction failed for %s: %s — using rule fallback", segment_id, exc)

    # ── Step 5: RULE FALLBACK ──
    if ml_result is None:
        matched = match_event(signature)
        if not matched.is_significant:
            return None
        rule_event_type = matched.event_type
        rule_confidence = matched.confidence
        source_path = "rule"
    else:
        rule_event_type, rule_confidence = ml_result

    # ── Step 6: Graph reasoning (unchanged) ──
    reasoning = reason_over_neighbors(graph, segment_id, neighbor_deviation_lookup)
    final_confidence = max(0.0, min(1.0, rule_confidence + reasoning.confidence_delta))

    if final_confidence < settings.EVENT_CONFIDENCE_THRESHOLD:
        logger.debug(
            "%s: confidence dropped below threshold after graph reasoning (%.3f) [%s]",
            segment_id, final_confidence, source_path,
        )
        return None

    event = Event(
        event_id=_next_event_id(db),
        event_type=rule_event_type,
        region_id=segment.region_id,
        primary_segment_id=segment_id,
        start_time=as_of,
        end_time=as_of,  # updated by future "close out" pass
        duration_hours=0,
        confidence=round(final_confidence, 3),
        severity=round(final_confidence, 3),
        affected_neighbors=";".join(reasoning.supporting_neighbors or neighbor_ids),
        source="detected",
    )
    event_repo.add(event)
    logger.info(
        "Recorded event %s: %s on %s (confidence=%.3f, via=%s)",
        event.event_id, event.event_type, segment_id, final_confidence, source_path,
    )
    return event
