"""
Route Optimization
----------------------
Thin wrapper around NetworkX's Dijkstra/A* — no need to hand-roll these,
NetworkX's implementations are well-tested. The only project-specific
logic is the heuristic function for A* (straight-line time estimate)
and wiring in the repriced graph from cost_model.py.
"""
from dataclasses import dataclass

import networkx as nx

from app.utils.geo_utils import haversine_m


@dataclass
class RouteResult:
    path: list[str]
    total_travel_time_s: float
    algorithm_used: str


def shortest_path_dijkstra(g: nx.DiGraph, origin: str, destination: str) -> RouteResult:
    path = nx.dijkstra_path(g, origin, destination, weight="weight")
    total = nx.dijkstra_path_length(g, origin, destination, weight="weight")
    return RouteResult(path=path, total_travel_time_s=total, algorithm_used="dijkstra")


def _astar_time_heuristic(g: nx.DiGraph, avg_speed_kmph: float = 30.0):
    """Straight-line-distance-based admissible heuristic. Needs each
    node to carry lat/lon — attach these when building the graph if you
    want A* available (graph_builder.py currently omits them for
    Dijkstra-only use; add mid_lat/mid_lon per node to enable this)."""
    def heuristic(u, v):
        if "mid_lat" not in g.nodes[u] or "mid_lat" not in g.nodes[v]:
            return 0.0  # falls back to Dijkstra-equivalent behavior
        d_m = haversine_m(g.nodes[u]["mid_lat"], g.nodes[u]["mid_lon"],
                           g.nodes[v]["mid_lat"], g.nodes[v]["mid_lon"])
        return d_m / (avg_speed_kmph * 1000 / 3600)
    return heuristic


def shortest_path_astar(g: nx.DiGraph, origin: str, destination: str) -> RouteResult:
    heuristic = _astar_time_heuristic(g)
    path = nx.astar_path(g, origin, destination, heuristic=heuristic, weight="weight")
    total = nx.path_weight(g, path, weight="weight")
    return RouteResult(path=path, total_travel_time_s=total, algorithm_used="astar")
