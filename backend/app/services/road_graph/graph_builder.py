"""
Road Connectivity Graph
-------------------------
Builds the NetworkX graph that both the Graph Reasoning layer and the
Routing layer operate on. Nodes = segments (NOT intersections — this
matches the project's "segment as fundamental unit" design, so edge
costs attach naturally to travel time along a segment). Two segments
get an edge if they share an intersection (i.e. one is in the other's
neighbor_segments list).

This is real, working code — it's cheap to get right and everything
else depends on it, so there's no stub here.
"""
import networkx as nx

from app.models.segment import Segment


def build_segment_graph(segments: list[Segment]) -> nx.DiGraph:
    """Directed graph: edge (A -> B) exists if B is reachable from A.
    Edge weight = A's own travel_time (time cost of TRAVERSING A before
    reaching B) — this is what the routing layer reprices when an event
    hits segment A."""
    g = nx.DiGraph()

    for seg in segments:
        base_travel_time_s = seg.segment_length_m / max(seg.max_speed_kmph * 1000 / 3600, 1)
        g.add_node(
            seg.segment_id,
            road_name=seg.road_name,
            region_id=seg.region_id,
            base_travel_time_s=base_travel_time_s,
            current_travel_time_s=base_travel_time_s,  # routing.cost_model mutates this
        )

    for seg in segments:
        neighbor_ids = [s for s in (seg.neighbor_segments or "").split(";") if s]
        for n in neighbor_ids:
            if g.has_node(n):
                g.add_edge(seg.segment_id, n, weight=g.nodes[seg.segment_id]["current_travel_time_s"])
                g.add_edge(n, seg.segment_id, weight=g.nodes[n]["current_travel_time_s"])

    return g


def get_neighbors(g: nx.DiGraph, segment_id: str, depth: int = 1) -> list[str]:
    """All segment_ids within `depth` hops — used by both graph
    reasoning (confidence boosting) and the event's `affected_neighbors`
    output field."""
    if segment_id not in g:
        return []
    lengths = nx.single_source_shortest_path_length(g, segment_id, cutoff=depth)
    return [n for n in lengths if n != segment_id]
