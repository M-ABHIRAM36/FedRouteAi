import pytest

from app.core.constants import RoadType
from app.services.geo_v2.network import normalize_overpass_json


def _point(node_id: int) -> dict[str, float]:
    points = {
        1: (17.000, 78.000),
        2: (17.001, 78.001),
        3: (17.002, 78.002),
        4: (17.001, 78.000),
        5: (17.001, 78.002),
        6: (17.003, 78.003),
    }
    lat, lon = points[node_id]
    return {"lat": lat, "lon": lon}


def _way(way_id, nodes, tags):
    return {
        "type": "way",
        "id": way_id,
        "nodes": nodes,
        "geometry": [_point(node_id) for node_id in nodes],
        "tags": {"highway": "residential", **tags},
    }


def _small_osm():
    return {
        "elements": [
            _way(100, [1, 2, 3], {"name": "Main Road", "highway": "primary", "maxspeed": "50 mph", "lanes": "4;2"}),
            _way(200, [4, 2, 5], {"name": "Cross Road", "highway": "secondary", "oneway": "yes", "bridge": "yes"}),
            _way(300, [3, 6], {"highway": "motorway_link", "oneway": "-1", "tunnel": "building_passage", "junction": "roundabout"}),
        ]
    }


def test_normalizes_and_splits_ways_while_preserving_vertices():
    network = normalize_overpass_json(_small_osm())

    assert len(network.segments) == 5
    main = [segment for segment in network.segments if segment.osm_way_id == 100]
    assert len(main) == 2
    assert main[0].geometry == ((78.000, 17.000), (78.001, 17.001))
    assert main[1].geometry == ((78.001, 17.001), (78.002, 17.002))
    assert main[0].road_type is RoadType.ARTERIAL
    assert main[0].max_speed_kmph == pytest.approx(80.467)
    assert main[0].lanes == 4
    assert main[0].length_m > 0
    assert all(segment.segment_id.startswith("GEO_") and len(segment.segment_id) <= 30 for segment in network.segments)
    assert all(segment.region_id in {f"REGION_{number:02d}" for number in range(1, 9)} for segment in network.segments)


def test_transitions_honor_forward_and_reverse_oneway_directions():
    network = normalize_overpass_json(_small_osm())
    by_way = {}
    for segment in network.segments:
        by_way.setdefault(segment.osm_way_id, []).append(segment)

    cross_before, cross_after = by_way[200]
    reverse = by_way[300][0]
    transitions = {(item.from_segment_id, item.to_segment_id) for item in network.transitions}

    assert (cross_before.segment_id, cross_after.segment_id) in transitions
    assert (cross_after.segment_id, cross_before.segment_id) not in transitions
    assert reverse.is_reversed
    assert (reverse.start_node_id, reverse.end_node_id) == (6, 3)
    assert any(item.from_segment_id == reverse.segment_id and item.via_node_id == 3 for item in network.transitions)
    assert not any(item.to_segment_id == reverse.segment_id and item.via_node_id == 3 for item in network.transitions)


def test_output_is_stable_and_metadata_is_normalized():
    first = normalize_overpass_json(_small_osm())
    second = normalize_overpass_json(_small_osm())
    reverse = next(segment for segment in first.segments if segment.osm_way_id == 300)
    cross = next(segment for segment in first.segments if segment.osm_way_id == 200)

    assert first == second
    assert reverse.road_name == "Unnamed Road"
    assert reverse.road_type is RoadType.HIGHWAY_LINK
    assert reverse.tunnel and reverse.junction == "roundabout"
    assert cross.bridge


def test_rejects_malformed_geometry():
    data = _small_osm()
    data["elements"][0]["geometry"] = data["elements"][0]["geometry"][:-1]

    with pytest.raises(ValueError, match="matching nodes and geometry"):
        normalize_overpass_json(data)


def test_rejects_zero_length_geometry_edge():
    data = _small_osm()
    data["elements"][0]["geometry"][1] = data["elements"][0]["geometry"][0]

    with pytest.raises(ValueError, match="duplicate coordinates"):
        normalize_overpass_json(data)
