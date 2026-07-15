"""Route optimization endpoint — uses the process-wide graph cache
(app/services/road_graph/graph_cache.py) instead of rebuilding the graph
from the DB on every call. Event penalties are cheap to reapply per
request (pure in-memory graph copy + reweight), so only the expensive
part (fetching + building from all segments) is cached."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.services.road_graph.graph_cache import GRAPH_CACHE
from app.services.routing.cost_model import apply_event_penalties
from app.services.routing.path_finder import shortest_path_dijkstra
from app.schemas.route import RouteRequest, RouteResponse

router = APIRouter(prefix="/routes", tags=["routes"])


@router.post("", response_model=RouteResponse)
def compute_route(req: RouteRequest, db: Session = Depends(get_db)):
    g = GRAPH_CACHE.get(db)

    rerouted_due_to = []
    if req.avoid_active_events:
        active_events = EventRepository(db).get_active_all()
        affected_ids = {e.primary_segment_id for e in active_events}
        rerouted_due_to = [e.event_id for e in active_events if e.primary_segment_id in affected_ids]
        g = apply_event_penalties(g, affected_ids)

    result = shortest_path_dijkstra(g, req.origin_segment_id, req.destination_segment_id)
    return RouteResponse(
        path=result.path,
        total_travel_time_s=result.total_travel_time_s,
        rerouted_due_to=rerouted_due_to,
    )


@router.post("/refresh-graph", status_code=204)
def refresh_graph_cache(db: Session = Depends(get_db)):
    """Manual invalidation hook — call this after bulk-adding/removing
    segments outside the normal event-driven flow (events themselves
    don't need this; their penalty is applied per-request, not baked
    into the cached structure)."""
    GRAPH_CACHE.refresh(db)
