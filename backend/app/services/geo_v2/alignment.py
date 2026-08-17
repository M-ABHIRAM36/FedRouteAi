"""Spatial quality reporting for generated canonical-network observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from shapely.geometry import LineString, Point

from app.services.geo_v2.network import CanonicalNetwork
from app.utils.geo_utils import METERS_PER_DEG_LAT, meters_per_deg_lon


@dataclass(frozen=True, slots=True)
class SpatialAlignmentReport:
    total: int
    valid: int
    invalid: int
    mean_m: float
    p95_m: float
    max_m: float


def spatial_alignment_report(
    observations: Iterable[Mapping[str, Any]],
    network: CanonicalNetwork,
    *,
    valid_tolerance_m: float = 1.0,
) -> SpatialAlignmentReport:
    """Measure point-to-LineString distance in a local equirectangular projection."""
    if valid_tolerance_m < 0:
        raise ValueError("valid_tolerance_m must be non-negative")
    segments = {segment.segment_id: segment for segment in network.segments}
    reference_lat = (network.bbox[1] + network.bbox[3]) / 2.0
    lon_scale = meters_per_deg_lon(reference_lat)

    distances: list[float] = []
    invalid = 0
    total = 0
    lines = {
        segment_id: LineString(
            [(lon * lon_scale, lat * METERS_PER_DEG_LAT) for lon, lat in segment.geometry]
        )
        for segment_id, segment in segments.items()
    }
    for observation in observations:
        total += 1
        segment_id = str(observation.get("segment_id", ""))
        try:
            point = Point(
                float(observation["lon"]) * lon_scale,
                float(observation["lat"]) * METERS_PER_DEG_LAT,
            )
            distance = float(lines[segment_id].distance(point))
        except (KeyError, TypeError, ValueError):
            invalid += 1
            continue
        if not math.isfinite(distance):
            invalid += 1
            continue
        distances.append(distance)
        if distance > valid_tolerance_m:
            invalid += 1

    ordered = sorted(distances)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1) if ordered else 0
    return SpatialAlignmentReport(
        total=total,
        valid=total - invalid,
        invalid=invalid,
        mean_m=sum(ordered) / len(ordered) if ordered else 0.0,
        p95_m=ordered[p95_index] if ordered else 0.0,
        max_m=ordered[-1] if ordered else 0.0,
    )
