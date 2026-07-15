"""
Edge Cost Repricing
----------------------
Applies event penalties to the road graph before every routing query:
current_travel_time = base_travel_time * penalty_factor, exactly as
specified in the project brief. Real, working code — this is cheap and
everything in routing depends on getting it right.
"""
import networkx as nx

from app.core.config import settings


def apply_event_penalties(g: nx.DiGraph, active_event_segment_ids: set[str], penalty_factor: float | None = None) -> nx.DiGraph:
    """Returns a NEW graph with edge weights repriced — never mutates the
    caller's graph in place, so the "clean" graph stays reusable."""
    penalty_factor = penalty_factor or settings.ROUTE_EVENT_PENALTY_FACTOR
    g2 = g.copy()

    for node_id, data in g2.nodes(data=True):
        base = data["base_travel_time_s"]
        current = base * penalty_factor if node_id in active_event_segment_ids else base
        data["current_travel_time_s"] = current

    for u, v, data in g2.edges(data=True):
        data["weight"] = g2.nodes[u]["current_travel_time_s"]

    return g2


def reset_penalties(g: nx.DiGraph) -> nx.DiGraph:
    return apply_event_penalties(g, active_event_segment_ids=set(), penalty_factor=1.0)
