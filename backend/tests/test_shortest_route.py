from datetime import datetime

import pytest

from app.core.constants import RoadDirection, RoadType
from app.repositories.geo_v2_repository import GeoV2Repository
from app.services.geo_v2.network import CanonicalNetwork, CanonicalSegment, CanonicalTransition
from app.services.road_graph.geo_v2_graph_cache import GeoV2GraphCache
from app.services.routing.shortest_route import NoRouteError, RouteInputError, ShortestRouteService


NETWORK_SOURCE = "osm_geo_v2"
NETWORK_VERSION = "routing-test-v1"


def _segment(segment_id, start_node, end_node, geometry, length=100.0, speed=36.0):
    return CanonicalSegment(
        segment_id=segment_id,
        osm_way_id=start_node,
        start_node_id=start_node,
        end_node_id=end_node,
        geometry=geometry,
        road_name=f"Road {segment_id}",
        highway="residential",
        road_type=RoadType.RESIDENTIAL,
        region_id="REGION_01",
        length_m=length,
        max_speed_kmph=speed,
        lanes=2,
        one_way=True,
        is_reversed=False,
        road_direction=RoadDirection.ONE_WAY,
        bridge=False,
        tunnel=False,
        junction=None,
    )


def _network():
    segments = (
        _segment("ROUTE_A", 1, 2, ((78.2900, 17.5100), (78.2910, 17.5105)), 100),
        _segment("ROUTE_B", 2, 3, ((78.2910, 17.5105), (78.2920, 17.5110), (78.2930, 17.5105)), 200),
        _segment("ROUTE_C", 3, 4, ((78.2930, 17.5105), (78.2940, 17.5100)), 300),
        _segment("ROUTE_ISOLATED", 5, 6, ((78.2960, 17.5130), (78.2970, 17.5135)), 100),
    )
    transitions = (
        CanonicalTransition("ROUTE_A", "ROUTE_B", 2),
        CanonicalTransition("ROUTE_B", "ROUTE_C", 3),
    )
    return CanonicalNetwork(segments, transitions, (78.29, 17.51, 78.297, 17.5135))


@pytest.fixture()
def routing_repository(db_session):
    repository = GeoV2Repository(db_session)
    repository.replace_network(
        _network(),
        network_source=NETWORK_SOURCE,
        network_version=NETWORK_VERSION,
        imported_at=datetime(2026, 8, 21),
    )
    return repository


def test_directed_shortest_route_snaps_and_uses_persisted_geometry(routing_repository):
    result = ShortestRouteService(routing_repository, GeoV2GraphCache()).calculate(
        origin_lat=17.51005,
        origin_lon=78.29005,
        destination_lat=17.51005,
        destination_lon=78.29395,
        network_source=NETWORK_SOURCE,
        network_version=NETWORK_VERSION,
    )

    assert result.ordered_segment_ids == ["ROUTE_A", "ROUTE_B", "ROUTE_C"]
    assert result.snapped_origin.segment_id == "ROUTE_A"
    assert result.snapped_destination.segment_id == "ROUTE_C"
    assert result.snapped_origin.distance_to_road_m < 10
    assert result.distance_m == pytest.approx(575.69, abs=0.01)
    assert result.estimated_duration_s == pytest.approx(57.57, abs=0.01)
    assert result.geometry == [
        pytest.approx((78.29006078, 17.51003039), abs=1e-7), (78.2910, 17.5105),
        (78.2920, 17.5110), (78.2930, 17.5105), pytest.approx((78.29393922, 17.51003039), abs=1e-7),
    ]


def test_same_segment_route_uses_only_the_directed_subsection(routing_repository):
    result = ShortestRouteService(routing_repository, GeoV2GraphCache()).calculate(
        origin_lat=17.5102,
        origin_lon=78.2904,
        destination_lat=17.51035,
        destination_lon=78.2907,
        network_source=NETWORK_SOURCE,
        network_version=NETWORK_VERSION,
    )
    assert result.ordered_segment_ids == ["ROUTE_A"]
    assert result.distance_m < 100
    assert result.geometry[0] == pytest.approx((result.snapped_origin.lon, result.snapped_origin.lat))
    assert result.geometry[-1] == pytest.approx((result.snapped_destination.lon, result.snapped_destination.lat))


def test_reverse_and_disconnected_routes_are_rejected(routing_repository):
    service = ShortestRouteService(routing_repository, GeoV2GraphCache())
    with pytest.raises(NoRouteError, match="no directed route"):
        service.calculate(
            origin_lat=17.5100, origin_lon=78.2940,
            destination_lat=17.5100, destination_lon=78.2900,
            network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
        )
    with pytest.raises(NoRouteError, match="no directed route"):
        service.calculate(
            origin_lat=17.5100, origin_lon=78.2900,
            destination_lat=17.5134, destination_lon=78.2969,
            network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
        )


def test_invalid_and_identical_locations_are_rejected(routing_repository):
    service = ShortestRouteService(routing_repository, GeoV2GraphCache())
    with pytest.raises(RouteInputError, match="different locations"):
        service.calculate(
            origin_lat=17.51, origin_lon=78.29,
            destination_lat=17.51, destination_lon=78.29,
            network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
        )
    with pytest.raises(RouteInputError, match="no routable road"):
        service.calculate(
            origin_lat=0, origin_lon=0,
            destination_lat=0, destination_lon=0.01,
            network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
        )


def test_prediction_summary_is_informational(routing_repository):
    common = {
        "source_id": "live-source", "run_id": "live-run",
        "timestamp": datetime(2026, 8, 21, 10), "confidence": 0.9,
        "class_probabilities": {}, "model_version": "geo-v2-test",
        "historical_baseline": {}, "current_deviation": {},
    }
    routing_repository.save_predictions([
        {**common, "segment_id": "ROUTE_A", "predicted_label": "normal"},
        {**common, "segment_id": "ROUTE_B", "predicted_label": "congestion"},
    ])

    result = ShortestRouteService(routing_repository, GeoV2GraphCache()).calculate(
        origin_lat=17.5100, origin_lon=78.2900,
        destination_lat=17.5100, destination_lon=78.2940,
        network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
        source_id="live-source", run_id="live-run",
    )

    assert result.predictions.counts == {"normal": 1, "congestion": 1}
    assert result.predictions.abnormal_segment_count == 1
    assert "This route contains predicted congestion." in result.predictions.warnings
    assert "Predictions are unavailable for 1 route segments." in result.predictions.warnings


def test_graph_cache_loads_each_network_once(routing_repository, monkeypatch):
    cache = GeoV2GraphCache()
    calls = 0
    original = routing_repository.load_network

    def counted_load(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(routing_repository, "load_network", counted_load)
    cache.get(routing_repository, NETWORK_SOURCE, NETWORK_VERSION)
    cache.get(routing_repository, NETWORK_SOURCE, NETWORK_VERSION)
    assert calls == 1
