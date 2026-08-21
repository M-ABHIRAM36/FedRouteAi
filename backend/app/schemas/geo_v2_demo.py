from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DemoScenario(str, Enum):
    NORMAL = "normal"
    CONGESTION = "congestion"
    ACCIDENT = "accident"


class GeoV2DemoCreateIn(BaseModel):
    scenario: DemoScenario = DemoScenario.CONGESTION
    vehicle_count: int = Field(default=250, ge=100, le=1_000)
    random_seed: int = 42
    ordered_route_segment_ids: list[str] = Field(min_length=3, max_length=500)
    route_distance_m: float = Field(ge=1_500)


class GeoV2DemoRunOut(BaseModel):
    source_id: str
    run_id: str
    scenario: DemoScenario
    status: str
    simulation_time: datetime
    tick_number: int
    vehicle_count: int
    network_source: str
    network_version: str
    corridor_segment_ids: list[str]
    route_distance_m: float
    disturbance_segment_id: str | None
    model_feature_count: int = 23
    history_ticks: int = 3
    cadence_seconds: int = 120


class GeoV2DemoStepOut(GeoV2DemoRunOut):
    accepted_observations: int
    observed_segments: int
    predictions_available: int
    ingestion_ms: float
    inference_ms: float
    labels_in_telemetry: int = 0
    event_ids_in_telemetry: int = 0
