"""Pure normalization of OSM Overpass ``out tags geom`` road data."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.core.constants import RoadDirection, RoadType
from app.utils.geo_utils import haversine_m


Coordinate = tuple[float, float]  # GeoJSON order: (longitude, latitude).

_HIGHWAY_TYPES: dict[str, RoadType] = {
    "motorway": RoadType.ARTERIAL,
    "trunk": RoadType.ARTERIAL,
    "primary": RoadType.ARTERIAL,
    "secondary": RoadType.COLLECTOR,
    "tertiary": RoadType.COLLECTOR,
    "unclassified": RoadType.RESIDENTIAL,
    "residential": RoadType.RESIDENTIAL,
    "living_street": RoadType.RESIDENTIAL,
    "service": RoadType.RESIDENTIAL,
    "track": RoadType.RESIDENTIAL,
}
_DRIVABLE_HIGHWAYS = frozenset(_HIGHWAY_TYPES) | frozenset({
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
})
_DEFAULT_SPEEDS = {
    RoadType.RESIDENTIAL: 30.0,
    RoadType.COLLECTOR: 40.0,
    RoadType.ARTERIAL: 60.0,
    RoadType.HIGHWAY_LINK: 50.0,
}
_DEFAULT_LANES = {
    RoadType.RESIDENTIAL: 2,
    RoadType.COLLECTOR: 2,
    RoadType.ARTERIAL: 4,
    RoadType.HIGHWAY_LINK: 2,
}
_TRUE_VALUES = frozenset({"yes", "true", "1"})
_FALSE_VALUES = frozenset({"no", "false", "0"})


@dataclass(frozen=True, slots=True)
class CanonicalSegment:
    segment_id: str
    osm_way_id: int
    start_node_id: int
    end_node_id: int
    geometry: tuple[Coordinate, ...]
    road_name: str
    highway: str
    road_type: RoadType
    region_id: str
    length_m: float
    max_speed_kmph: float
    lanes: int
    one_way: bool
    is_reversed: bool
    road_direction: RoadDirection
    bridge: bool
    tunnel: bool
    junction: str | None


@dataclass(frozen=True, slots=True)
class CanonicalTransition:
    from_segment_id: str
    to_segment_id: str
    via_node_id: int


@dataclass(frozen=True, slots=True)
class CanonicalNetwork:
    segments: tuple[CanonicalSegment, ...]
    transitions: tuple[CanonicalTransition, ...]
    bbox: tuple[float, float, float, float]  # min lon, min lat, max lon, max lat


@dataclass(frozen=True, slots=True)
class _Way:
    way_id: int
    nodes: tuple[int, ...]
    geometry: tuple[Coordinate, ...]
    tags: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _SegmentDraft:
    segment_id: str
    osm_way_id: int
    start_node_id: int
    end_node_id: int
    geometry: tuple[Coordinate, ...]
    road_name: str
    highway: str
    road_type: RoadType
    length_m: float
    max_speed_kmph: float
    lanes: int
    one_way: bool
    is_reversed: bool
    bridge: bool
    tunnel: bool
    junction: str | None


def normalize_overpass_json(data: Mapping[str, Any]) -> CanonicalNetwork:
    """Normalize an Overpass response without a database or network access."""
    ways = _parse_ways(data)
    if not ways:
        return CanonicalNetwork(segments=(), transitions=(), bbox=(0.0, 0.0, 0.0, 0.0))

    shared_nodes = _shared_nodes(ways)
    drafts = tuple(
        draft
        for way in sorted(ways, key=lambda item: item.way_id)
        for draft in _split_way(way, shared_nodes)
    )
    bbox = _bbox(draft.geometry for draft in drafts)
    segments = tuple(
        CanonicalSegment(
            segment_id=draft.segment_id,
            osm_way_id=draft.osm_way_id,
            start_node_id=draft.start_node_id,
            end_node_id=draft.end_node_id,
            geometry=draft.geometry,
            road_name=draft.road_name,
            highway=draft.highway,
            road_type=draft.road_type,
            region_id=_region_id(_line_midpoint(draft.geometry), bbox),
            length_m=draft.length_m,
            max_speed_kmph=draft.max_speed_kmph,
            lanes=draft.lanes,
            one_way=draft.one_way,
            is_reversed=draft.is_reversed,
            road_direction=(RoadDirection.ONE_WAY if draft.one_way else RoadDirection.BIDIRECTIONAL),
            bridge=draft.bridge,
            tunnel=draft.tunnel,
            junction=draft.junction,
        )
        for draft in drafts
    )
    return CanonicalNetwork(
        segments=segments,
        transitions=_derive_transitions(segments),
        bbox=bbox,
    )


def load_overpass_json(path: str | Path) -> CanonicalNetwork:
    """Load and normalize an Overpass JSON file from disk."""
    with Path(path).open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise ValueError("Overpass document must be a JSON object")
    return normalize_overpass_json(data)


def _parse_ways(data: Mapping[str, Any]) -> tuple[_Way, ...]:
    elements = data.get("elements", [])
    if not isinstance(elements, list):
        raise ValueError("Overpass 'elements' must be a list")

    ways: list[_Way] = []
    seen_ids: set[int] = set()
    for element in elements:
        if not isinstance(element, Mapping) or element.get("type") != "way":
            continue
        tags = element.get("tags", {})
        if not isinstance(tags, Mapping) or str(tags.get("highway", "")).lower() not in _DRIVABLE_HIGHWAYS:
            continue
        try:
            way_id = int(element["id"])
            nodes = tuple(int(node_id) for node_id in element["nodes"])
            raw_geometry = element["geometry"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("OSM road way has invalid id or nodes") from exc
        if way_id in seen_ids:
            raise ValueError(f"duplicate OSM way id {way_id}")
        if not isinstance(raw_geometry, list) or len(nodes) != len(raw_geometry) or len(nodes) < 2:
            raise ValueError(f"OSM way {way_id} must have matching nodes and geometry")
        geometry = tuple(_parse_coordinate(point, way_id) for point in raw_geometry)
        if any(nodes[index] == nodes[index + 1] for index in range(len(nodes) - 1)):
            raise ValueError(f"OSM way {way_id} has consecutive duplicate nodes")
        if any(first == second for first, second in zip(geometry, geometry[1:])):
            raise ValueError(f"OSM way {way_id} has consecutive duplicate coordinates")
        seen_ids.add(way_id)
        ways.append(_Way(way_id, nodes, geometry, tags))
    return tuple(ways)


def _parse_coordinate(point: Any, way_id: int) -> Coordinate:
    if not isinstance(point, Mapping):
        raise ValueError(f"OSM way {way_id} has invalid geometry")
    try:
        lat = float(point["lat"])
        lon = float(point["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"OSM way {way_id} has invalid geometry") from exc
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"OSM way {way_id} has out-of-range geometry")
    return lon, lat


def _shared_nodes(ways: tuple[_Way, ...]) -> frozenset[int]:
    counts: Counter[int] = Counter()
    for way in ways:
        counts.update(set(way.nodes))
    return frozenset(node_id for node_id, count in counts.items() if count > 1)


def _split_way(way: _Way, shared_nodes: frozenset[int]) -> tuple[_SegmentDraft, ...]:
    cuts = [0]
    cuts.extend(index for index in range(1, len(way.nodes) - 1) if way.nodes[index] in shared_nodes)
    cuts.append(len(way.nodes) - 1)

    road_type = _road_type(str(way.tags["highway"]))
    one_way_value = _oneway(way.tags)
    drafts: list[_SegmentDraft] = []
    for start_index, end_index in zip(cuts, cuts[1:]):
        nodes = way.nodes[start_index:end_index + 1]
        geometry = way.geometry[start_index:end_index + 1]
        original_start, original_end = nodes[0], nodes[-1]
        is_reversed = one_way_value == -1
        if is_reversed:
            nodes = tuple(reversed(nodes))
            geometry = tuple(reversed(geometry))
        length_m = _line_length_m(geometry)
        if length_m <= 0:
            raise ValueError(f"OSM way {way.way_id} contains zero-length geometry")
        drafts.append(
            _SegmentDraft(
                segment_id=_segment_id(way.way_id, original_start, original_end),
                osm_way_id=way.way_id,
                start_node_id=nodes[0],
                end_node_id=nodes[-1],
                geometry=geometry,
                road_name=_road_name(way.tags),
                highway=str(way.tags["highway"]).strip().lower(),
                road_type=road_type,
                length_m=length_m,
                max_speed_kmph=_maxspeed(way.tags.get("maxspeed"), road_type),
                lanes=_lanes(way.tags.get("lanes"), road_type),
                one_way=one_way_value != 0,
                is_reversed=is_reversed,
                bridge=_tag_bool(way.tags.get("bridge")),
                tunnel=_tag_bool(way.tags.get("tunnel")),
                junction=_optional_text(way.tags.get("junction")),
            )
        )
    return tuple(drafts)


def _road_type(highway: str) -> RoadType:
    value = highway.strip().lower()
    if value.endswith("_link"):
        return RoadType.HIGHWAY_LINK
    return _HIGHWAY_TYPES.get(value, RoadType.RESIDENTIAL)


def _road_name(tags: Mapping[str, Any]) -> str:
    for key in ("name", "ref", "official_name"):
        value = _optional_text(tags.get(key))
        if value:
            return value
    return "Unnamed Road"


def _oneway(tags: Mapping[str, Any]) -> int:
    raw = str(tags.get("oneway", "")).strip().lower()
    if raw == "-1" or raw == "reverse":
        return -1
    if raw in _TRUE_VALUES:
        return 1
    if raw in _FALSE_VALUES:
        return 0
    junction = str(tags.get("junction", "")).strip().lower()
    return 1 if junction in {"roundabout", "circular"} else 0


def _maxspeed(raw: Any, road_type: RoadType) -> float:
    text = str(raw or "").strip().lower()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return _DEFAULT_SPEEDS[road_type]
    speed = float(match.group())
    if "mph" in text:
        speed *= 1.609344
    return round(speed, 3) if speed > 0 else _DEFAULT_SPEEDS[road_type]


def _lanes(raw: Any, road_type: RoadType) -> int:
    match = re.search(r"\d+", str(raw or ""))
    if not match:
        return _DEFAULT_LANES[road_type]
    return max(1, int(match.group()))


def _tag_bool(raw: Any) -> bool:
    value = str(raw or "").strip().lower()
    if value in _FALSE_VALUES or not value:
        return False
    return value in _TRUE_VALUES or value not in {"none", "null"}


def _optional_text(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _segment_id(way_id: int, start_node_id: int, end_node_id: int) -> str:
    identity = f"{way_id}:{start_node_id}:{end_node_id}".encode("ascii")
    return f"GEO_{hashlib.blake2s(identity, digest_size=12).hexdigest()}"


def _line_length_m(geometry: tuple[Coordinate, ...]) -> float:
    return sum(
        haversine_m(first[1], first[0], second[1], second[0])
        for first, second in zip(geometry, geometry[1:])
    )


def _bbox(geometries: Any) -> tuple[float, float, float, float]:
    points = [point for geometry in geometries for point in geometry]
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _line_midpoint(geometry: tuple[Coordinate, ...]) -> Coordinate:
    total = _line_length_m(geometry)
    target = total / 2
    travelled = 0.0
    for first, second in zip(geometry, geometry[1:]):
        edge_length = haversine_m(first[1], first[0], second[1], second[0])
        if travelled + edge_length >= target:
            ratio = (target - travelled) / edge_length
            return (
                first[0] + (second[0] - first[0]) * ratio,
                first[1] + (second[1] - first[1]) * ratio,
            )
        travelled += edge_length
    return geometry[-1]


def _region_id(point: Coordinate, bbox: tuple[float, float, float, float]) -> str:
    min_lon, min_lat, max_lon, max_lat = bbox
    column = _grid_index(point[0], min_lon, max_lon, 4)
    row = _grid_index(point[1], min_lat, max_lat, 2)
    return f"REGION_{row * 4 + column + 1:02d}"


def _grid_index(value: float, minimum: float, maximum: float, cells: int) -> int:
    if maximum == minimum:
        return 0
    return min(int((value - minimum) / (maximum - minimum) * cells), cells - 1)


def _derive_transitions(segments: tuple[CanonicalSegment, ...]) -> tuple[CanonicalTransition, ...]:
    entries: defaultdict[int, list[CanonicalSegment]] = defaultdict(list)
    exits: defaultdict[int, list[CanonicalSegment]] = defaultdict(list)
    for segment in segments:
        entries[segment.start_node_id].append(segment)
        exits[segment.end_node_id].append(segment)
        if not segment.one_way:
            entries[segment.end_node_id].append(segment)
            exits[segment.start_node_id].append(segment)

    transitions = {
        CanonicalTransition(source.segment_id, target.segment_id, node_id)
        for node_id in exits.keys() & entries.keys()
        for source in exits[node_id]
        for target in entries[node_id]
        if source.segment_id != target.segment_id
    }
    return tuple(
        sorted(
            transitions,
            key=lambda item: (item.from_segment_id, item.to_segment_id, item.via_node_id),
        )
    )
