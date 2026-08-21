"""Small, dependency-light helpers shared by Geo V2 command-line tools."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping
import csv
import json

from app.core.constants import EventType
from app.services.geo_v2.inference import TelemetryAggregate


NETWORK_SOURCE = "osm_geo_v2"
NETWORK_VERSION = "beeramguda-osm-20260506"


def scrub_observations(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Remove simulation truth before a row can cross the telemetry boundary."""
    return [
        {**row, "label": EventType.NORMAL.value, "event_id": ""}
        for row in rows
    ]


def aggregate_observations(rows: Iterable[Mapping[str, object]]) -> dict[str, TelemetryAggregate]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["segment_id"])].append(row)
    result = {}
    for segment_id, items in grouped.items():
        speeds = [float(item["speed_kmph"]) for item in items]
        mean = sum(speeds) / len(speeds)
        variance = sum((speed - mean) ** 2 for speed in speeds) / max(len(speeds) - 1, 1)
        result[segment_id] = TelemetryAggregate(
            avg_speed_kmph=mean,
            vehicle_count=len({str(item["vehicle_id"]) for item in items}),
            uturn_rate=sum(bool(item.get("is_uturn_flag", False)) for item in items) / len(items),
            std_speed_kmph=variance**0.5,
        )
    return result


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
