from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from time import perf_counter
from typing import Protocol

from app.core.constants import EventType
from app.schemas.gps_ping import LiveGPSBatchIn
from app.utils.time_utils import utcnow


class LiveBatchConflictError(Exception):
    pass


class LiveBatchValidationError(Exception):
    pass


class LiveIngestionRepositoryProtocol(Protocol):
    def segment_regions(self, segment_ids: set[str]) -> dict[str, str]: ...
    def get_batch(self, source_id: str, run_id: str, batch_id: str): ...
    def persist_batch(self, batch_data: dict, observations: list[dict], states: list[dict]): ...
    def rollback(self) -> None: ...


@dataclass(frozen=True)
class LiveIngestionResult:
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


def _payload_hash(batch: LiveGPSBatchIn) -> str:
    payload = batch.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result_from_receipt(receipt, *, duplicates: int, validation_ms: float, database_ms: float, total_ms: float):
    return LiveIngestionResult(
        accepted=0 if duplicates else receipt.accepted_count,
        rejected=0,
        duplicates=duplicates,
        timestamp=receipt.observed_at,
        regions=receipt.region_count,
        segments=receipt.segment_count,
        average_speed_kmph=receipt.average_speed_kmph,
        validation_ms=round(validation_ms, 2),
        database_ms=round(database_ms, 2),
        total_ms=round(total_ms, 2),
    )


def ingest_live_batch(batch: LiveGPSBatchIn, repository: LiveIngestionRepositoryProtocol) -> LiveIngestionResult:
    started = perf_counter()
    payload_hash = _payload_hash(batch)
    existing = repository.get_batch(batch.source_id, batch.run_id, batch.batch_id)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise LiveBatchConflictError("batch identity was already used with different content")
        elapsed = (perf_counter() - started) * 1000
        return _result_from_receipt(
            existing,
            duplicates=len(batch.observations),
            validation_ms=elapsed,
            database_ms=0.0,
            total_ms=elapsed,
        )

    observation_ids = [item.observation_id for item in batch.observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise LiveBatchValidationError("observation_id values must be unique within a batch")

    segment_ids = {item.segment_id for item in batch.observations}
    segment_regions = repository.segment_regions(segment_ids)
    missing = sorted(segment_ids - segment_regions.keys())
    if missing:
        raise LiveBatchValidationError(f"unknown segment_id values: {missing[:5]}")

    for item in batch.observations:
        expected_region = segment_regions[item.segment_id]
        if item.region_id != expected_region:
            raise LiveBatchValidationError(
                f"segment {item.segment_id} belongs to {expected_region}, not {item.region_id}"
            )
        if item.label == EventType.NORMAL and item.event_id:
            raise LiveBatchValidationError("normal observations must not carry event_id")
        if item.label != EventType.NORMAL and not item.event_id:
            raise LiveBatchValidationError("event observations require event_id")

    validation_ms = (perf_counter() - started) * 1000
    observed_at = max(item.timestamp for item in batch.observations)
    average_speed = round(sum(item.speed_kmph for item in batch.observations) / len(batch.observations), 2)
    received_at = utcnow()
    grouped: dict[str, list] = defaultdict(list)
    for item in batch.observations:
        grouped[item.segment_id].append(item)

    states = []
    for segment_id, items in grouped.items():
        labels = Counter(item.label.value for item in items if item.label != EventType.NORMAL)
        current_event = labels.most_common(1)[0][0] if labels else EventType.NORMAL.value
        vehicle_count = len({item.vehicle_id for item in items})
        states.append({
            "segment_id": segment_id,
            "region_id": segment_regions[segment_id],
            "latest_timestamp": max(item.timestamp for item in items),
            "vehicle_count": vehicle_count,
            "average_speed_kmph": round(sum(item.speed_kmph for item in items) / len(items), 2),
            "density": float(vehicle_count),
            "current_event": current_event,
            "available": current_event != EventType.ROAD_BLOCK.value,
            "last_updated": received_at,
        })

    observations = [{
        "observation_id": item.observation_id,
        "segment_id": item.segment_id,
        "region_id": item.region_id,
        "vehicle_id": item.vehicle_id,
        "vehicle_type": item.vehicle_type.value,
        "lat": item.lat,
        "lon": item.lon,
        "speed_kmph": item.speed_kmph,
        "heading_deg": item.heading_deg,
        "timestamp": item.timestamp,
        "is_uturn_flag": item.is_uturn_flag,
        "label": item.label.value,
        "event_id": item.event_id or None,
    } for item in batch.observations]

    database_started = perf_counter()
    try:
        receipt = repository.persist_batch({
            "source_id": batch.source_id,
            "run_id": batch.run_id,
            "batch_id": batch.batch_id,
            "tick_number": batch.tick_number,
            "payload_hash": payload_hash,
            "observed_at": observed_at,
            "received_at": received_at,
            "accepted_count": len(observations),
            "segment_count": len(grouped),
            "region_count": len({item.region_id for item in batch.observations}),
            "average_speed_kmph": average_speed,
            "network_source": batch.network_source,
            "network_version": batch.network_version,
        }, observations, states)
    except Exception:
        repository.rollback()
        raise
    database_ms = (perf_counter() - database_started) * 1000
    total_ms = (perf_counter() - started) * 1000
    return _result_from_receipt(
        receipt,
        duplicates=0,
        validation_ms=validation_ms,
        database_ms=database_ms,
        total_ms=total_ms,
    )
