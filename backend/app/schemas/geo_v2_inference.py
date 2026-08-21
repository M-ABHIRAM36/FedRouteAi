"""API contracts for database-backed Geo V2 telemetry inference."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TelemetryAggregateIn(_StrictSchema):
    avg_speed_kmph: float = Field(ge=0)
    vehicle_count: int = Field(ge=0)
    uturn_rate: float = Field(ge=0, le=1)
    std_speed_kmph: float = Field(ge=0)
    window_minutes: float = Field(default=20.0, gt=0)


class NeighborAggregateIn(_StrictSchema):
    speed_ratio: float = Field(ge=0)
    density_ratio: float = Field(ge=0)


class TelemetryInferenceRequest(_StrictSchema):
    source_id: str = Field(default="manual-inference", max_length=60)
    run_id: str = Field(default="manual-inference", max_length=80)
    segment_id: str
    as_of: datetime
    telemetry: TelemetryAggregateIn
    neighbors: list[NeighborAggregateIn] = Field(default_factory=list)


class TelemetryInferenceResponse(BaseModel):
    segment_id: str
    timestamp: datetime
    model_version: str
    prediction: str | None
    confidence: float | None
    probabilities: dict[str, float]
    baseline: dict[str, float | int]
    deviations: dict[str, float]


class GeoV2TelemetryIn(_StrictSchema):
    avg_speed_kmph: float = Field(ge=0)
    speed_std_kmph: float = Field(ge=0)
    vehicle_count: float = Field(ge=0)
    occupancy: float = Field(ge=0, le=1)
    flow_rate_vph: float = Field(ge=0)
    stopped_fraction: float = Field(ge=0, le=1)


class GeoV2NeighborIn(GeoV2TelemetryIn):
    segment_id: str


class GeoV2InferenceItem(_StrictSchema):
    source_id: str = Field(default="geo-v2-inference", max_length=60)
    run_id: str = Field(default="geo-v2-inference", max_length=80)
    segment_id: str
    as_of: datetime
    telemetry: GeoV2TelemetryIn
    neighbors: list[GeoV2NeighborIn] = Field(default_factory=list)


class GeoV2InferenceRequest(GeoV2InferenceItem):
    pass


class GeoV2BatchInferenceRequest(_StrictSchema):
    items: list[GeoV2InferenceItem] = Field(min_length=1, max_length=500)


class GeoV2InferenceResponse(BaseModel):
    status: str
    segment_id: str
    region: str | None
    timestamp: datetime
    model_version: str | None
    feature_version: str
    prediction: str | None
    predicted_label: str | None
    confidence: float | None
    confidence_is_calibrated: bool = False
    probabilities: dict[str, float]
    baseline: dict[str, float | int]
    deviations: dict[str, float]


class GeoV2BatchInferenceResponse(BaseModel):
    results: list[GeoV2InferenceResponse]
