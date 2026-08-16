from __future__ import annotations

from datetime import timedelta

from app.core.config import settings
from app.core.constants import EventType
from app.schemas.live_map import (
    LiveMapEventOut,
    LiveMapSegmentStateOut,
    LiveMapSnapshotOut,
    LiveMapSummaryOut,
    LiveMapVehicleOut,
)
from app.utils.time_utils import utcnow


class LiveMapNotFoundError(Exception):
    pass


def build_live_map_snapshot(repository, source_id: str | None = None, run_id: str | None = None) -> LiveMapSnapshotOut:
    receipt = repository.latest_batch(source_id, run_id)
    if receipt is None:
        raise LiveMapNotFoundError("no live ingestion batch is available")

    stale_after = max(settings.LIVE_TICK_INTERVAL_SECONDS * 3, 10.0)
    fresh_after = receipt.observed_at - timedelta(seconds=stale_after)
    positions = repository.latest_vehicle_positions(
        receipt.source_id,
        receipt.run_id,
        receipt.observed_at,
        fresh_after,
    )
    states = repository.segment_states(receipt.source_id, receipt.run_id)

    vehicles = [LiveMapVehicleOut(
        vehicle_id=row.vehicle_id,
        vehicle_type=row.vehicle_type,
        segment_id=row.segment_id,
        region_id=row.region_id,
        lat=row.lat,
        lon=row.lon,
        speed_kmph=row.speed_kmph,
        heading_deg=row.heading_deg,
        timestamp=row.timestamp,
    ) for row in positions]
    segment_states = [LiveMapSegmentStateOut.model_validate({
        "segment_id": state.segment_id,
        "region_id": state.region_id,
        "latest_timestamp": state.latest_timestamp,
        "vehicle_count": state.vehicle_count,
        "average_speed_kmph": state.average_speed_kmph,
        "density": state.density,
        "current_event": state.current_event,
        "available": state.available,
        "last_updated": state.last_updated,
    }) for state in states]

    events_by_id = {}
    for row in positions:
        if row.label != EventType.NORMAL.value and row.event_id:
            events_by_id[row.event_id] = LiveMapEventOut(
                event_id=row.event_id,
                segment_id=row.segment_id,
                region_id=row.region_id,
                event_type=row.label,
                timestamp=row.timestamp,
            )
    events = sorted(events_by_id.values(), key=lambda event: event.event_id)
    average_speed = sum(row.speed_kmph for row in positions) / len(positions) if positions else 0.0

    return LiveMapSnapshotOut(
        source_id=receipt.source_id,
        run_id=receipt.run_id,
        batch_id=receipt.batch_id,
        tick_number=receipt.tick_number,
        observed_at=receipt.observed_at,
        received_at=receipt.received_at,
        server_time=utcnow(),
        poll_interval_seconds=settings.LIVE_TICK_INTERVAL_SECONDS,
        stale_after_seconds=stale_after,
        segments=segment_states,
        vehicles=vehicles,
        events=events,
        summary=LiveMapSummaryOut(
            vehicle_count=len(vehicles),
            active_segments=len({row.segment_id for row in positions}),
            active_events=len(events),
            average_speed_kmph=round(average_speed, 2),
            latest_update=receipt.observed_at,
        ),
    )
