"""Directed distance routing over persisted Geo V2 OSM segments."""
from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter

import networkx as nx

from app.core.config import settings
from app.repositories.geo_v2_repository import GeoV2Repository
from app.services.road_graph.geo_v2_graph_cache import GEO_V2_GRAPH_CACHE, GeoV2GraphCache, GeoV2RouteGraph
from app.utils.geo_utils import haversine_m, meters_per_deg_lon


class RouteInputError(ValueError):
    pass


class RoutingNetworkNotFoundError(LookupError):
    pass


class NoRouteError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class SnappedPoint:
    lat: float
    lon: float
    segment_id: str
    distance_to_road_m: float
    fraction: float


@dataclass(frozen=True, slots=True)
class PredictionSummary:
    available: bool
    source_id: str | None
    run_id: str | None
    counts: dict[str, int]
    abnormal_segment_count: int
    covered_segment_count: int
    coverage_ratio: float
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class ShortestRouteResult:
    network_source: str
    network_version: str
    origin: tuple[float, float]
    destination: tuple[float, float]
    snapped_origin: SnappedPoint
    snapped_destination: SnappedPoint
    distance_m: float
    estimated_duration_s: float
    computation_time_ms: float
    ordered_segment_ids: list[str]
    geometry: list[tuple[float, float]]
    predictions: PredictionSummary
    cost_basis: str


class ShortestRouteService:
    def __init__(self, repository, cache: GeoV2GraphCache = GEO_V2_GRAPH_CACHE) -> None:
        self.repository = repository
        self.cache = cache

    def calculate(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        network_source: str,
        network_version: str,
        source_id: str | None = None,
        run_id: str | None = None,
        avoid_segment_ids: set[str] | None = None,
    ) -> ShortestRouteResult:
        started = perf_counter()
        if haversine_m(origin_lat, origin_lon, destination_lat, destination_lon) < 1.0:
            raise RouteInputError("origin and destination must be different locations")
        try:
            route_graph = self.cache.get(self.repository, network_source, network_version)
        except ValueError as exc:
            raise RoutingNetworkNotFoundError(
                f"routing network {network_source}/{network_version} was not found"
            ) from exc
        origin = snap_to_route_graph(route_graph, origin_lat, origin_lon)
        destination = snap_to_route_graph(route_graph, destination_lat, destination_lon)
        excluded = set(avoid_segment_ids or ())
        excluded.discard(origin.segment_id)
        excluded.discard(destination.segment_id)
        graph = route_graph.graph
        if excluded:
            graph = graph.copy()
            graph.remove_nodes_from(excluded)
        try:
            path = nx.dijkstra_path(
                graph, origin.segment_id, destination.segment_id, weight="weight",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            raise NoRouteError("no directed route connects the selected locations") from exc

        segments = [route_graph.segments[segment_id] for segment_id in path]
        distance_m = sum(segment.length_m for segment in segments)
        if len(segments) == 1:
            if destination.fraction < origin.fraction:
                raise NoRouteError("no directed route connects the selected locations")
            distance_m = segments[0].length_m * (destination.fraction - origin.fraction)
            duration_s = distance_m / max(segments[0].max_speed_kmph, 1.0) * 3.6
            geometry = trim_segment_geometry(list(segments[0].geometry), origin.fraction, destination.fraction)
        else:
            distance_m -= segments[0].length_m * origin.fraction
            distance_m -= segments[-1].length_m * (1.0 - destination.fraction)
            duration_s = sum(
                segment.length_m / max(segment.max_speed_kmph, 1.0) * 3.6 for segment in segments
            )
            duration_s -= segments[0].length_m * origin.fraction / max(segments[0].max_speed_kmph, 1.0) * 3.6
            duration_s -= segments[-1].length_m * (1.0 - destination.fraction) / max(segments[-1].max_speed_kmph, 1.0) * 3.6
            geometry = assemble_route_geometry(segments, origin, destination)
        predictions = prediction_summary(self.repository, path, source_id, run_id)
        return ShortestRouteResult(
            network_source=network_source,
            network_version=network_version,
            origin=(origin_lat, origin_lon),
            destination=(destination_lat, destination_lon),
            snapped_origin=origin,
            snapped_destination=destination,
            distance_m=distance_m,
            estimated_duration_s=duration_s,
            computation_time_ms=(perf_counter() - started) * 1000,
            ordered_segment_ids=path,
            geometry=geometry,
            predictions=predictions,
            cost_basis="distance with explicit segment exclusions" if excluded else "distance",
        )


def snap_to_route_graph(graph: GeoV2RouteGraph, lat: float, lon: float) -> SnappedPoint:
    best: SnappedPoint | None = None
    distance_before = 0.0
    for segment in graph.segments.values():
        segment_length = sum(haversine_m(start[1], start[0], end[1], end[0]) for start, end in zip(segment.geometry, segment.geometry[1:]))
        traversed = 0.0
        for start, end in zip(segment.geometry, segment.geometry[1:]):
            edge_length = haversine_m(start[1], start[0], end[1], end[0])
            snapped_lat, snapped_lon, distance, fraction = _project_to_line(lat, lon, start, end)
            if best is None or distance < best.distance_to_road_m:
                best = SnappedPoint(
                    snapped_lat, snapped_lon, segment.segment_id, distance,
                    (traversed + edge_length * fraction) / max(segment_length, 1.0),
                )
            traversed += edge_length
    if best is None or best.distance_to_road_m > settings.ROUTE_SNAP_MAX_DISTANCE_M:
        raise RouteInputError(
            f"no routable road found within {settings.ROUTE_SNAP_MAX_DISTANCE_M:.0f} m"
        )
    return best


def _project_to_line(
    lat: float, lon: float, start: tuple[float, float], end: tuple[float, float],
) -> tuple[float, float, float, float]:
    scale_lon = meters_per_deg_lon(lat)
    ax = (start[0] - lon) * scale_lon
    ay = (start[1] - lat) * 111_320.0
    bx = (end[0] - lon) * scale_lon
    by = (end[1] - lat) * 111_320.0
    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy
    fraction = 0.0 if denominator == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator))
    x, y = ax + fraction * dx, ay + fraction * dy
    return lat + y / 111_320.0, lon + x / scale_lon, math.hypot(x, y), fraction


def assemble_route_geometry(segments, origin: SnappedPoint, destination: SnappedPoint) -> list[tuple[float, float]]:
    coordinates: list[tuple[float, float]] = []
    for index, segment in enumerate(segments):
        points = list(segment.geometry)
        if index == 0:
            points = _trim_from_fraction(points, origin.fraction)
        if index == len(segments) - 1:
            points = _trim_to_fraction(points, destination.fraction)
        if coordinates and points and coordinates[-1] == points[0]:
            points = points[1:]
        coordinates.extend(points)
    return coordinates


def trim_segment_geometry(points: list[tuple[float, float]], start_fraction: float, end_fraction: float) -> list[tuple[float, float]]:
    start = _interpolate_point(points, start_fraction)
    end = _interpolate_point(points, end_fraction)
    total = sum(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:]))
    start_distance = total * start_fraction
    end_distance = total * end_fraction
    result = [start]
    traversed = 0.0
    for index, length in enumerate(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])):
        traversed += length
        if start_distance < traversed < end_distance:
            result.append(points[index + 1])
    if result[-1] != end:
        result.append(end)
    return result


def _interpolate_point(points: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    if fraction <= 0:
        return points[0]
    if fraction >= 1:
        return points[-1]
    lengths = [haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])]
    target = sum(lengths) * fraction
    traversed = 0.0
    for index, length in enumerate(lengths):
        if traversed + length >= target:
            part = (target - traversed) / max(length, 1.0)
            return (
                points[index][0] + (points[index + 1][0] - points[index][0]) * part,
                points[index][1] + (points[index + 1][1] - points[index][1]) * part,
            )
        traversed += length
    return points[-1]


def _trim_from_fraction(points: list[tuple[float, float]], fraction: float) -> list[tuple[float, float]]:
    snapped = _interpolate_point(points, fraction)
    target = sum(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])) * fraction
    traversed = 0.0
    result = [snapped]
    for index, length in enumerate(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])):
        traversed += length
        if traversed > target:
            result.extend(points[index + 1:])
            break
    return result


def _trim_to_fraction(points: list[tuple[float, float]], fraction: float) -> list[tuple[float, float]]:
    snapped = _interpolate_point(points, fraction)
    target = sum(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])) * fraction
    traversed = 0.0
    result: list[tuple[float, float]] = []
    for index, length in enumerate(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(points, points[1:])):
        if traversed + length >= target:
            result.append(snapped)
            break
        result.append(points[index + 1])
        traversed += length
    return [points[0], *result] if result and result[0] != points[0] else result


def build_shortest_route_service(db) -> ShortestRouteService:
    return ShortestRouteService(GeoV2Repository(db))


def prediction_summary(repository, path: list[str], source_id: str | None, run_id: str | None) -> PredictionSummary:
    if not source_id or not run_id:
        return PredictionSummary(False, source_id, run_id, {}, 0, 0, 0.0, ["Current prediction data was not requested."])
    rows = repository.latest_predictions_for_segments(source_id, run_id, set(path))
    labels = {row.segment_id: row.predicted_label for row in rows if row.predicted_label}
    counts: dict[str, int] = {}
    for segment_id in path:
        label = labels.get(segment_id)
        if label:
            counts[label] = counts.get(label, 0) + 1
    abnormal = sum(count for label, count in counts.items() if label != "normal")
    warnings = [
        f"This route contains predicted {label.replace('_', ' ')}."
        for label, count in sorted(counts.items()) if label != "normal" and count > 0
    ]
    if len(labels) < len(path):
        warnings.append(f"Predictions are unavailable for {len(path) - len(labels)} route segments.")
    return PredictionSummary(
        bool(labels) and len(labels) == len(path), source_id, run_id, counts, abnormal,
        len(labels), len(labels) / len(path) if path else 0.0, warnings,
    )
