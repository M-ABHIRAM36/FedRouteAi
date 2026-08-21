"""Distance-based operations on canonical road polylines."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.geo_v2.network import Coordinate
from app.utils.geo_utils import bearing_deg, haversine_m


@dataclass(frozen=True, slots=True)
class PolylinePosition:
    coordinate: Coordinate
    heading_deg: float
    edge_index: int


def interpolate_polyline(
    geometry: tuple[Coordinate, ...],
    distance_m: float,
    *,
    reverse: bool = False,
) -> PolylinePosition:
    """Interpolate by cumulative geodesic edge length and return local heading."""
    if len(geometry) < 2:
        raise ValueError("a polyline requires at least two coordinates")
    points = tuple(reversed(geometry)) if reverse else geometry
    edge_lengths = tuple(
        haversine_m(first[1], first[0], second[1], second[0])
        for first, second in zip(points, points[1:])
    )
    total_m = sum(edge_lengths)
    if total_m <= 0:
        raise ValueError("a polyline must have positive length")

    remaining = min(max(distance_m, 0.0), total_m)
    for edge_index, (first, second, edge_m) in enumerate(
        zip(points, points[1:], edge_lengths)
    ):
        if remaining <= edge_m or edge_index == len(edge_lengths) - 1:
            ratio = min(remaining / edge_m, 1.0)
            coordinate = (
                first[0] + (second[0] - first[0]) * ratio,
                first[1] + (second[1] - first[1]) * ratio,
            )
            return PolylinePosition(
                coordinate=coordinate,
                heading_deg=bearing_deg(first[1], first[0], second[1], second[0]),
                edge_index=edge_index,
            )
        remaining -= edge_m
    raise AssertionError("unreachable polyline interpolation state")
