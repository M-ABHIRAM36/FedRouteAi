"""The event object shape — this IS the JSON contract described in the
project spec, delivered to navigation providers / traffic management /
smart-city platforms."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    segment_id: str
    event: str            # event_type, named to match the spec's JSON example
    confidence: float
    affected_neighbors: list[str]
    recommended_route: list[str] = []
    start_time: datetime
    end_time: datetime | None = None
