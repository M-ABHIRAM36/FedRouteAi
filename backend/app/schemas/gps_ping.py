"""What an ingestion client (mobile app / GPS logger) POSTs to /ingest.

Deliberately no per-ping device_id: a batch IS one device's trajectory
(that's what GPSBatchIn.device_id identifies), so a second identity
field on each individual ping would either have to always repeat the
same value or risk silently disagreeing with it — neither is useful,
and ingest.py's persistence logic reads only the batch-level id."""
from datetime import datetime

from pydantic import BaseModel, Field


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
