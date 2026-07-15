"""Route optimization request/response."""
from pydantic import BaseModel


class RouteRequest(BaseModel):
    origin_segment_id: str
    destination_segment_id: str
    avoid_active_events: bool = True


class RouteResponse(BaseModel):
    path: list[str]                 # ordered segment_ids
    total_travel_time_s: float
    rerouted_due_to: list[str] = [] # event_ids that forced a detour, if any
