"""Route optimization request/response."""
from pydantic import BaseModel, Field

from app.schemas.segment import LineStringGeometry


class RouteRequest(BaseModel):
    origin_segment_id: str
    destination_segment_id: str
    avoid_active_events: bool = True


class RouteResponse(BaseModel):
    path: list[str]                 # ordered segment_ids
    total_travel_time_s: float
    rerouted_due_to: list[str] = [] # event_ids that forced a detour, if any


class RoutePoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ShortestRouteRequest(BaseModel):
    origin: RoutePoint
    destination: RoutePoint
    network_source: str
    network_version: str
    source_id: str | None = None
    run_id: str | None = None
    avoid_segment_ids: list[str] = Field(default_factory=list, max_length=200)


class SnappedRoutePoint(RoutePoint):
    segment_id: str
    distance_to_road_m: float


class RoutePredictionSummary(BaseModel):
    available: bool
    source_id: str | None = None
    run_id: str | None = None
    counts: dict[str, int]
    abnormal_segment_count: int
    covered_segment_count: int
    coverage_ratio: float
    warnings: list[str]


class ShortestRouteResponse(BaseModel):
    network_source: str
    network_version: str
    algorithm: str
    cost_basis: str
    origin: RoutePoint
    destination: RoutePoint
    snapped_origin: SnappedRoutePoint
    snapped_destination: SnappedRoutePoint
    distance_m: float
    estimated_duration_s: float
    computation_time_ms: float
    segment_count: int
    ordered_segment_ids: list[str]
    geometry: LineStringGeometry
    predictions: RoutePredictionSummary
