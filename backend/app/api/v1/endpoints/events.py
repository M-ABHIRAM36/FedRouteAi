"""Active events endpoint — also computes `recommended_route` per event
by routing between the affected segment's neighbors around it, using
the same cached graph + penalty logic as /routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventOut
from app.services.road_graph.graph_cache import GRAPH_CACHE
from app.services.routing.cost_model import apply_event_penalties
from app.services.routing.path_finder import shortest_path_dijkstra
from app.core.logging_config import get_logger

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger(__name__)


def _recommended_route_around(db: Session, event, all_active_segment_ids: set[str]) -> list[str]:
    """Best-effort: route from the first affected neighbor to the last,
    avoiding every currently-active event segment (not just this one) —
    that's the same detour a live vehicle would actually need. Returns
    [] if there aren't at least two neighbors to route between, or no
    path exists once events are penalized (dead end, not an error)."""
    neighbor_ids = [s for s in (event.affected_neighbors or "").split(";") if s]
    if len(neighbor_ids) < 2:
        return []

    g = GRAPH_CACHE.get(db)
    g = apply_event_penalties(g, all_active_segment_ids)
    try:
        result = shortest_path_dijkstra(g, neighbor_ids[0], neighbor_ids[-1])
        return result.path
    except Exception:
        logger.debug("No route found around event %s", event.event_id)
        return []


@router.get("", response_model=list[EventOut])
def list_active_events(db: Session = Depends(get_db)):
    repo = EventRepository(db)
    rows = repo.get_active_all()
    all_active_segment_ids = {r.primary_segment_id for r in rows}

    out = []
    for r in rows:
        out.append(EventOut(
            event_id=r.event_id, segment_id=r.primary_segment_id, event=r.event_type,
            confidence=r.confidence,
            affected_neighbors=[s for s in (r.affected_neighbors or "").split(";") if s],
            recommended_route=_recommended_route_around(db, r, all_active_segment_ids),
            start_time=r.start_time, end_time=r.end_time,
        ))
    return out
