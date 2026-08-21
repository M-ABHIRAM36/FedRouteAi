from datetime import datetime

from app.core.constants import EventType, RoadDirection, RoadType
from app.schemas.geo_v2_inference import GeoV2InferenceItem
from app.schemas.geo_v2_demo import DemoScenario, GeoV2DemoCreateIn
from app.services.geo_v2.demo_runtime import GeoV2DemoRegistry, GeoV2DemoService, scrub_demo_observations
from app.services.geo_v2.network import CanonicalNetwork, CanonicalSegment, CanonicalTransition
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig


def _segment(index: int) -> CanonicalSegment:
    return CanonicalSegment(
        segment_id=f"S{index}", osm_way_id=index, start_node_id=index, end_node_id=index + 1,
        geometry=((78.30 + index * 0.001, 17.50), (78.301 + index * 0.001, 17.50)),
        road_name=f"Road {index}", highway="primary", road_type=RoadType.ARTERIAL,
        region_id="REGION_01", length_m=306.0, max_speed_kmph=40.0, lanes=2,
        one_way=True, is_reversed=False, road_direction=RoadDirection.ONE_WAY,
        bridge=False, tunnel=False, junction=None,
    )


def _network() -> CanonicalNetwork:
    segments = tuple(_segment(index) for index in range(1, 8))
    transitions = tuple(CanonicalTransition(f"S{index}", f"S{index + 1}", index + 1) for index in range(1, 7))
    return CanonicalNetwork(segments, transitions, (78.301, 17.50, 78.308, 17.50))


def test_controlled_routes_are_deterministic_and_follow_directed_geometry():
    config = SimulationConfig(
        vehicle_count=10, tick_seconds=1, simulation_speed=30, random_seed=9,
        start_time=datetime(2026, 8, 17, 8), controlled_route_share=1.0,
    )
    first = GeoV2Simulation(_network(), config)
    second = GeoV2Simulation(_network(), config)
    first.start()
    second.start()

    assert first.demo_corridors == second.demo_corridors
    assert [vehicle.route_segment_ids for vehicle in first.state.vehicles.values()] == [
        vehicle.route_segment_ids for vehicle in second.state.vehicles.values()
    ]
    before = {row["vehicle_id"]: row for row in first.observations()}
    after = {row["vehicle_id"]: row for row in first.tick()}
    assert first.state.last_transitions
    legal = {(item.from_segment_id, item.to_segment_id) for item in first.network.transitions}
    assert all((item.from_segment_id, item.to_segment_id) in legal for item in first.state.last_transitions)
    assert all(abs(after[key]["lon"] - before[key]["lon"]) < 0.003 for key in before)


def test_demo_corridors_preserve_revisited_segments(monkeypatch):
    simulation = GeoV2Simulation(
        _network(), SimulationConfig(vehicle_count=5, random_seed=2, controlled_route_share=0),
    )
    route = ["S1", "S2", "S3", "S2", "S4", "S5"]
    monkeypatch.setattr(simulation, "_deterministic_route", lambda *args, **kwargs: route)

    corridor = simulation._build_demo_corridors()[0]

    assert corridor == tuple(route)


def test_demo_registry_removes_expired_runs():
    registry = GeoV2DemoRegistry()
    request = GeoV2DemoCreateIn(scenario=DemoScenario.NORMAL, vehicle_count=100, random_seed=4, ordered_route_segment_ids=[f"S{i}" for i in range(1, 7)], route_distance_m=1600)
    run = registry.create(request, _network())
    run.last_accessed_at = 0

    try:
        registry.get(run.run_id)
    except LookupError:
        pass
    else:
        raise AssertionError("expired run remained active")
    assert not run.simulation.state.running


def test_demo_service_rejects_model_network_mismatch(monkeypatch):
    from app.ml.geo_v2.model_store import GEO_V2_MODEL_STORE

    monkeypatch.setattr(type(GEO_V2_MODEL_STORE), "network_version", property(lambda self: "wrong-network"))
    service = GeoV2DemoService(None, None, None, None)
    request = GeoV2DemoCreateIn(scenario=DemoScenario.NORMAL, vehicle_count=100, ordered_route_segment_ids=["S1", "S2", "S3"], route_distance_m=1600)

    try:
        service.create(request)
    except ValueError as error:
        assert "do not match" in str(error)
    else:
        raise AssertionError("network mismatch was accepted")


def test_scenario_truth_is_absent_from_model_input_and_scrubbed_from_telemetry():
    raw = [{"segment_id": "S1", "label": EventType.ACCIDENT.value, "event_id": "TRUTH_1"}]
    clean = scrub_demo_observations(raw)
    item = GeoV2InferenceItem.model_validate({
        "source_id": "geo-v2-demo", "run_id": "demo-test", "segment_id": "S1",
        "as_of": "2026-08-17T08:06:00", "telemetry": {
            "avg_speed_kmph": 4, "speed_std_kmph": 2, "vehicle_count": 20,
            "occupancy": 0.8, "flow_rate_vph": 10, "stopped_fraction": 0.7,
        },
    }).model_dump()

    assert clean[0]["label"] == EventType.NORMAL.value
    assert clean[0]["event_id"] == ""
    assert "label" not in item and "event_id" not in item
    assert "label" not in item["telemetry"] and "event_id" not in item["telemetry"]
