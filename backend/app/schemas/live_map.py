"""Normalized dynamic contract consumed by the live traffic map."""
from datetime import datetime

from pydantic import BaseModel


class LiveMapVehicleOut(BaseModel):
    vehicle_id: str
    vehicle_type: str
    segment_id: str
    region_id: str
    lat: float
    lon: float
    speed_kmph: float
    heading_deg: float
    timestamp: datetime


class LiveMapSegmentStateOut(BaseModel):
    segment_id: str
    region_id: str
    latest_timestamp: datetime
    vehicle_count: int
    average_speed_kmph: float
    density: float
    current_event: str
    available: bool
    last_updated: datetime
    predicted_event: str | None = None
    prediction_confidence: float | None = None
    prediction_model_version: str | None = None
    historical_baseline: dict | None = None
    current_deviation: dict | None = None


class LiveMapEventOut(BaseModel):
    event_id: str
    segment_id: str
    region_id: str
    event_type: str
    timestamp: datetime
    severity: float | None = None
    affected_segment_ids: list[str] = []
    source: str = "telemetry_ground_truth"


class LiveMapSummaryOut(BaseModel):
    vehicle_count: int
    active_segments: int
    active_events: int
    average_speed_kmph: float
    latest_update: datetime


class LiveMapSnapshotOut(BaseModel):
    source_id: str
    run_id: str
    batch_id: str
    tick_number: int
    observed_at: datetime
    received_at: datetime
    server_time: datetime
    poll_interval_seconds: float
    stale_after_seconds: float
    network_source: str | None = None
    network_version: str | None = None
    segments: list[LiveMapSegmentStateOut]
    vehicles: list[LiveMapVehicleOut]
    events: list[LiveMapEventOut]
    summary: LiveMapSummaryOut
