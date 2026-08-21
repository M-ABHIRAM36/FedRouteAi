"""Database-free scenario creation and graph propagation."""
from datetime import datetime, timedelta
from typing import Mapping, Sequence

from app.core.constants import EventType
from app.schemas.live_scenario import ScenarioItemIn
from app.services.geo_v2.network import CanonicalTransition


def build_scenario_rows(
    source_id: str,
    run_id: str,
    items: Sequence[ScenarioItemIn],
    segment_regions: Mapping[str, str],
    transitions: Sequence[CanonicalTransition],
    now: datetime,
    first_event_number: int = 1,
) -> list[dict]:
    upstream: dict[str, set[str]] = {}
    downstream: dict[str, set[str]] = {}
    for transition in transitions:
        downstream.setdefault(transition.from_segment_id, set()).add(transition.to_segment_id)
        upstream.setdefault(transition.to_segment_id, set()).add(transition.from_segment_id)

    rows = []
    for offset, item in enumerate(items):
        if item.segment_id not in segment_regions:
            raise ValueError(f"unknown segment_id: {item.segment_id}")
        affected = {item.segment_id}
        if item.type in {EventType.ACCIDENT, EventType.CONGESTION, EventType.CONSTRUCTION, EventType.ROAD_BLOCK}:
            affected.update(upstream.get(item.segment_id, ()))
        if item.type is EventType.DIVERSION:
            affected.update(downstream.get(item.segment_id, ()))
        starts = item.start_time or now
        rows.append({
            "event_id": f"G2E{first_event_number + offset:06d}",
            "source_id": source_id,
            "run_id": run_id,
            "event_type": item.type.value,
            "primary_segment_id": item.segment_id,
            "region_id": segment_regions[item.segment_id],
            "affected_segment_ids": sorted(affected),
            "severity": item.severity,
            "start_time": starts,
            "end_time": starts + timedelta(seconds=item.duration_seconds),
            "ground_truth_label": item.type.value,
            "status": "scheduled" if starts > now else "active",
            "created_at": now,
        })
    return rows
