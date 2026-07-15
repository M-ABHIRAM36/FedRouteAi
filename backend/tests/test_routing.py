from types import SimpleNamespace

from app.services.road_graph.graph_builder import build_segment_graph
from app.services.routing.cost_model import apply_event_penalties
from app.services.routing.path_finder import shortest_path_dijkstra


def _line_segments():
    return [
        SimpleNamespace(segment_id="A", road_name="A", region_id="R1", max_speed_kmph=40,
                         segment_length_m=200, neighbor_segments="B"),
        SimpleNamespace(segment_id="B", road_name="B", region_id="R1", max_speed_kmph=40,
                         segment_length_m=200, neighbor_segments="A;C"),
        SimpleNamespace(segment_id="C", road_name="C", region_id="R1", max_speed_kmph=40,
                         segment_length_m=200, neighbor_segments="B"),
    ]


def test_event_penalty_increases_route_cost():
    g = build_segment_graph(_line_segments())
    baseline = shortest_path_dijkstra(g, "A", "C")

    g_penalized = apply_event_penalties(g, active_event_segment_ids={"B"})
    penalized = shortest_path_dijkstra(g_penalized, "A", "C")

    assert penalized.total_travel_time_s > baseline.total_travel_time_s
    assert penalized.path == ["A", "B", "C"]  # only path available in this fixture
