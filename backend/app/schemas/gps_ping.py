"""What an ingestion client (mobile app / GPS logger) POSTs to /ingest.

Deliberately no per-ping device_id: a batch IS one device's trajectory
(that's what GPSBatchIn.device_id identifies), so a second identity
field on each individual ping would either have to always repeat the
same value or risk silently disagreeing with it — neither is useful,
and ingest.py's persistence logic reads only the batch-level id."""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import EventType, VehicleType


class GPSPingIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmph: float | None = Field(default=None, ge=0)
    heading_deg: float | None = Field(default=None, ge=0, le=360)
    timestamp: datetime


class GPSBatchIn(BaseModel):
    """Mobile apps should batch pings rather than POST one at a time —
    one batch per device per short time window (e.g. every 30-60s of
    driving), not one batch per entire trip, so ingestion latency for
    event detection stays low."""
    device_id: str
    pings: list[GPSPingIn]


class LiveGPSObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(min_length=1, max_length=100)
    segment_id: str = Field(min_length=1, max_length=30)
    region_id: str = Field(min_length=1, max_length=20)
    vehicle_id: str = Field(min_length=1, max_length=60)
    vehicle_type: VehicleType
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmph: float = Field(ge=0)
    heading_deg: float = Field(ge=0, le=360)
    timestamp: datetime
    is_uturn_flag: bool = False
    label: EventType = EventType.NORMAL
    event_id: str = Field(default="", max_length=20)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_naive(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


class LiveGPSBatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=60)
    run_id: str = Field(min_length=1, max_length=80)
    batch_id: str = Field(min_length=1, max_length=80)
    tick_number: int = Field(ge=1)
    observations: list[LiveGPSObservationIn] = Field(min_length=1)


class LiveGPSBatchResult(BaseModel):
    accepted: int
    rejected: int
    duplicates: int
    timestamp: datetime
    regions: int
    segments: int
    average_speed_kmph: float
    validation_ms: float
    database_ms: float
    total_ms: float
