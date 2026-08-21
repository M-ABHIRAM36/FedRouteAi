from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.constants import EventType
from app.schemas.gps_ping import LiveGPSObservationIn
from app.services.geo_v2 import (
    DemoPhase,
    GeoV2Simulation,
    ScheduledDemo,
    SimulationConfig,
    interpolate_polyline,
    spatial_alignment_report,
)
from app.services.geo_v2.network import normalize_overpass_json
from app.utils.geo_utils import bearing_deg, haversine_m


def _network():
    points = {
        1: (17.0000, 78.0000),
        2: (17.0007, 78.0005),
        3: (17.0000, 78.0010),
        4: (17.0000, 78.0020),
        5: (17.0010, 78.0020),
        6: (17.0010, 78.0000),
        7: (16.9992, 78.0015),
    }

    def way(way_id: int, nodes: list[int], road: str = "residential") -> dict[str, object]:
        return {
            "type": "way",
            "id": way_id,
            "nodes": nodes,
            "geometry": [
                {"lat": points[node_id][0], "lon": points[node_id][1]}
                for node_id in nodes
            ],
            "tags": {
                "highway": road,
                "oneway": "yes",
                "lanes": "2",
                "maxspeed": "40",
                "name": f"Road {way_id}",
            },
        }

    return normalize_overpass_json({
        "elements": [
            way(100, [1, 2, 3], "primary"),  # Curved approach to a fork.
            way(200, [3, 4]),
            way(300, [4, 5]),
            way(400, [5, 6]),
            way(500, [6, 1]),
            way(600, [3, 7]),
            way(700, [7, 6]),
        ]
    })


def _by_way(network, way_id: int):
    return next(segment for segment in network.segments if segment.osm_way_id == way_id)


def _simulation(*, seed: int = 42, vehicles: int = 1_000, simulated_tick_seconds: float = 5.0):
    network = _network()
    simulation = GeoV2Simulation(
        network,
        SimulationConfig(
            vehicle_count=vehicles,
            tick_seconds=1.0,
            simulation_speed=simulated_tick_seconds,
            random_seed=seed,
            start_time=datetime(2026, 7, 7, 6, 0, 0),
        ),
        segment_context={_by_way(network, 300).segment_id: {"flood_prone": True}},
    )
    simulation.start()
    return simulation


def test_curved_polyline_uses_distance_interpolation_and_local_tangent_heading():
    segment = _by_way(_network(), 100)
    first_edge_m = haversine_m(17.0000, 78.0000, 17.0007, 78.0005)
    second_edge_m = haversine_m(17.0007, 78.0005, 17.0000, 78.0010)

    vertex = interpolate_polyline(segment.geometry, first_edge_m)
    second_half = interpolate_polyline(segment.geometry, first_edge_m + second_edge_m / 2)

    assert vertex.coordinate == pytest.approx((78.0005, 17.0007))
    assert second_half.coordinate == pytest.approx((78.00075, 17.00035))
    assert vertex.heading_deg == pytest.approx(
        bearing_deg(17.0000, 78.0000, 17.0007, 78.0005)
    )
    assert second_half.heading_deg == pytest.approx(
        bearing_deg(17.0007, 78.0005, 17.0000, 78.0010)
    )
    assert abs(vertex.heading_deg - second_half.heading_deg) > 45


def test_vehicles_are_persistent_and_only_make_legal_one_way_transitions():
    simulation = _simulation(vehicles=1_000, simulated_tick_seconds=30.0)
    identities = set(simulation.state.vehicles)
    legal = {
        (transition.from_segment_id, transition.to_segment_id, transition.via_node_id)
        for transition in simulation.network.transitions
    }

    for _ in range(8):
        observations = simulation.tick()
        assert set(simulation.state.vehicles) == identities
        assert len(observations) == 1_000
        assert all(
            (record.from_segment_id, record.to_segment_id, record.via_node_id) in legal
            for record in simulation.state.last_transitions
        )

    assert simulation.state.last_transitions
    assert all(vehicle.direction == 1 for vehicle in simulation.state.vehicles.values())


def test_event_lifecycle_composition_flood_context_and_directed_propagation():
    simulation = _simulation(vehicles=80)
    approach = _by_way(simulation.network, 100)
    target = _by_way(simulation.network, 200)
    downstream = _by_way(simulation.network, 300)

    congestion = simulation.schedule_event(
        EventType.CONGESTION, target.segment_id, duration_minutes=10, severity=0.5
    )
    simulation.schedule_event(
        EventType.ACCIDENT, target.segment_id, duration_minutes=5, severity=0.9
    )
    state = simulation.state.flow_states[target.segment_id]
    assert state.active_event_types == (EventType.ACCIDENT, EventType.CONGESTION)
    assert simulation.state.flow_states[approach.segment_id].upstream_pressure > 0
    assert simulation.state.flow_states[approach.segment_id].downstream_pressure == 0
    assert simulation.state.flow_states[downstream.segment_id].downstream_pressure > 0
    assert simulation.state.flow_states[downstream.segment_id].upstream_pressure == 0

    with pytest.raises(ValueError, match="provided segment context"):
        simulation.schedule_event(EventType.FLOOD, target.segment_id, duration_minutes=10)
    flood = simulation.schedule_event(EventType.FLOOD, downstream.segment_id, duration_minutes=10)
    assert flood.event_type is EventType.FLOOD

    simulation.state.current_time += timedelta(minutes=6)
    simulation.tick()
    assert simulation.state.flow_states[target.segment_id].active_event_types == (EventType.CONGESTION,)
    simulation.state.current_time = congestion.end_time
    simulation.tick()
    assert simulation.state.flow_states[target.segment_id].active_event_types == ()


def test_every_non_normal_event_type_is_supported():
    simulation = _simulation(vehicles=10)
    ordinary = _by_way(simulation.network, 200).segment_id
    flood_prone = _by_way(simulation.network, 300).segment_id

    scheduled = {
        simulation.schedule_event(
            event_type,
            flood_prone if event_type is EventType.FLOOD else ordinary,
            duration_minutes=10,
            event_id=f"ALL_{event_type.value.upper()}",
        ).event_type
        for event_type in EventType
        if event_type is not EventType.NORMAL
    }

    assert scheduled == set(EventType) - {EventType.NORMAL}


def test_blocked_road_is_excluded_and_diversion_changes_bounded_route_choice():
    baseline = _simulation(seed=8, vehicles=400)
    diverted = _simulation(seed=8, vehicles=400)
    blocked = _simulation(seed=8, vehicles=400)
    approach_id = _by_way(baseline.network, 100).segment_id
    direct_id = _by_way(baseline.network, 200).segment_id

    for simulation in (baseline, diverted, blocked):
        approach = simulation._segments[approach_id]
        for vehicle in simulation.state.vehicles.values():
            vehicle.segment_id = approach_id
            vehicle.direction = 1
            vehicle.distance_m = approach.length_m - 0.01
            vehicle.destination_segment_id = _by_way(simulation.network, 300).segment_id
    diverted.schedule_event(EventType.DIVERSION, direct_id, duration_minutes=30)
    blocked.schedule_event(EventType.ROAD_BLOCK, direct_id, duration_minutes=30)

    baseline.tick()
    diverted.tick()
    blocked.tick()
    baseline_direct = sum(record.to_segment_id == direct_id for record in baseline.state.last_transitions)
    diverted_direct = sum(record.to_segment_id == direct_id for record in diverted.state.last_transitions)

    assert diverted_direct < baseline_direct
    assert not any(record.to_segment_id == direct_id for record in blocked.state.last_transitions)
    assert blocked.state.flow_states[direct_id].available_for_entry is False


def test_road_damage_has_distinctly_higher_speed_variance_than_congestion():
    congestion = _simulation(seed=19, vehicles=500)
    damage = _simulation(seed=19, vehicles=500)
    target_id = _by_way(congestion.network, 400).segment_id
    for simulation in (congestion, damage):
        segment = simulation._segments[target_id]
        for vehicle in simulation.state.vehicles.values():
            vehicle.segment_id = target_id
            vehicle.distance_m = segment.length_m / 2
    congestion.schedule_event(EventType.CONGESTION, target_id, duration_minutes=30)
    damage.schedule_event(EventType.ROAD_DAMAGE, target_id, duration_minutes=30)

    congestion.tick()
    damage.tick()

    assert damage.state.flow_states[target_id].speed_variance > congestion.state.flow_states[target_id].speed_variance


def test_seed_start_tick_and_outputs_are_reproducible_and_ingestion_compatible():
    first = _simulation(seed=73, vehicles=40)
    second = _simulation(seed=73, vehicles=40)

    first_rows = first.tick()
    second_rows = second.tick()

    assert first_rows == second_rows
    assert first.state.flow_states == second.state.flow_states
    assert first.state.current_time == datetime(2026, 7, 7, 6, 0, 5)
    assert all(LiveGPSObservationIn.model_validate(row) for row in first_rows)


def test_accelerated_five_hour_demo_and_flow_metrics():
    simulation = _simulation(seed=5, simulated_tick_seconds=600.0)
    target_id = _by_way(simulation.network, 200).segment_id
    demo = ScheduledDemo.install(simulation, target_id)
    phases = [demo.phase]

    for _ in range(30):
        simulation.tick()
        phases.append(demo.phase)

    assert set(phases) >= {
        DemoPhase.NORMAL,
        DemoPhase.CONGESTION,
        DemoPhase.CONGESTION_ACCIDENT,
        DemoPhase.CONSTRUCTION_CONGESTION,
        DemoPhase.RECOVERY,
        DemoPhase.COMPLETE,
    }
    assert simulation.state.current_time == simulation.config.start_time + timedelta(hours=5)
    assert len(simulation.state.vehicles) == 1_000
    state = simulation.state.flow_states[target_id]
    assert state.vehicle_count >= 0
    assert state.density_vehicles_per_km_lane >= 0
    assert state.speed_variance >= 0
    assert state.flow_rate_vph >= 0
    assert 0 <= state.occupancy <= 1
    assert state.capacity_vehicles > 0 and state.capacity_vph > 0
    assert state.travel_time_seconds > 0


def test_spatial_alignment_report_uses_point_to_polyline_distance():
    simulation = _simulation(vehicles=100)
    rows = simulation.tick()
    rows.append({"segment_id": "missing", "lat": 17.0, "lon": 78.0})
    rows.append({
        "segment_id": rows[0]["segment_id"],
        "lat": float(rows[0]["lat"]) + 0.001,
        "lon": rows[0]["lon"],
    })

    report = spatial_alignment_report(rows, simulation.network, valid_tolerance_m=0.5)

    assert report.total == 102
    assert report.valid == 100
    assert report.invalid == 2
    assert report.mean_m > 0
    assert report.p95_m < report.max_m
    assert report.max_m > 20
