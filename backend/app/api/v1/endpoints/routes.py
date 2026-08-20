"""Route optimization endpoint — uses the process-wide graph cache
(app/services/road_graph/graph_cache.py) instead of rebuilding the graph
from the DB on every call. Event penalties are cheap to reapply per
request (pure in-memory graph copy + reweight), so only the expensive
part (fetching + building from all segments) is cached."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.services.road_graph.graph_cache import GRAPH_CACHE
from app.services.routing.cost_model import apply_event_penalties
from app.services.routing.path_finder import shortest_path_dijkstra
from app.schemas.route import (
    LineStringGeometry,
    RoutePoint,
    RoutePredictionSummary,
    RouteRequest,
    RouteResponse,
    ShortestRouteRequest,
    ShortestRouteResponse,
    SnappedRoutePoint,
)
from app.services.routing.shortest_route import (
    NoRouteError,
    RouteInputError,
    RoutingNetworkNotFoundError,
    ShortestRouteService,
    build_shortest_route_service,
)

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


@router.post("/shortest", response_model=ShortestRouteResponse)
def compute_shortest_route(req: ShortestRouteRequest, db: Session = Depends(get_db)):
    try:
        result = build_shortest_route_service(db).calculate(
            origin_lat=req.origin.lat,
            origin_lon=req.origin.lon,
            destination_lat=req.destination.lat,
            destination_lon=req.destination.lon,
            network_source=req.network_source,
            network_version=req.network_version,
            source_id=req.source_id,
            run_id=req.run_id,
        )
    except RouteInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RoutingNetworkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoRouteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ShortestRouteResponse(
        network_source=result.network_source,
        network_version=result.network_version,
        algorithm="Dijkstra",
        cost_basis="distance",
        origin=RoutePoint(lat=result.origin[0], lon=result.origin[1]),
        destination=RoutePoint(lat=result.destination[0], lon=result.destination[1]),
        snapped_origin=SnappedRoutePoint(
            lat=result.snapped_origin.lat,
            lon=result.snapped_origin.lon,
            segment_id=result.snapped_origin.segment_id,
            distance_to_road_m=result.snapped_origin.distance_to_road_m,
        ),
        snapped_destination=SnappedRoutePoint(
            lat=result.snapped_destination.lat,
            lon=result.snapped_destination.lon,
            segment_id=result.snapped_destination.segment_id,
            distance_to_road_m=result.snapped_destination.distance_to_road_m,
        ),
        distance_m=result.distance_m,
        estimated_duration_s=result.estimated_duration_s,
        computation_time_ms=result.computation_time_ms,
        segment_count=len(result.ordered_segment_ids),
        ordered_segment_ids=result.ordered_segment_ids,
        geometry=LineStringGeometry(coordinates=result.geometry),
        predictions=RoutePredictionSummary(
            available=result.predictions.available,
            source_id=result.predictions.source_id,
            run_id=result.predictions.run_id,
            counts=result.predictions.counts,
            abnormal_segment_count=result.predictions.abnormal_segment_count,
            warnings=result.predictions.warnings,
        ),
    )


@router.post("/refresh-graph", status_code=204)
def refresh_graph_cache(db: Session = Depends(get_db)):
    """Manual invalidation hook — call this after bulk-adding/removing
    segments outside the normal event-driven flow (events themselves
    don't need this; their penalty is applied per-request, not baked
    into the cached structure)."""
    GRAPH_CACHE.refresh(db)
