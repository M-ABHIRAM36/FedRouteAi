"""Versioned cache for the persisted directed Geo V2 routing graph."""
from dataclasses import dataclass
from threading import Lock

import networkx as nx

from app.services.geo_v2.network import CanonicalNetwork, CanonicalSegment


@dataclass(frozen=True, slots=True)
class GeoV2RouteGraph:
    network_source: str
    network_version: str
    graph: nx.DiGraph
    segments: dict[str, CanonicalSegment]


def build_geo_v2_route_graph(
    network: CanonicalNetwork, network_source: str, network_version: str,
) -> GeoV2RouteGraph:
    if not network.segments:
        raise ValueError("routing network was not found")
    segments = {segment.segment_id: segment for segment in network.segments}
    graph = nx.DiGraph()
    graph.add_nodes_from(segments)
    for transition in network.transitions:
        destination = segments.get(transition.to_segment_id)
        if transition.from_segment_id in segments and destination is not None:
            graph.add_edge(
                transition.from_segment_id,
                transition.to_segment_id,
                weight=destination.length_m,
            )
    return GeoV2RouteGraph(network_source, network_version, graph, segments)


class GeoV2GraphCache:
    def __init__(self) -> None:
        self._graphs: dict[tuple[str, str], GeoV2RouteGraph] = {}
        self._lock = Lock()

    def get(self, repository, network_source: str, network_version: str) -> GeoV2RouteGraph:
        key = (network_source, network_version)
        cached = self._graphs.get(key)
        if cached is not None:
            return cached
        with self._lock:
            cached = self._graphs.get(key)
            if cached is None:
                network = repository.load_network(network_version, network_source)
                cached = build_geo_v2_route_graph(network, network_source, network_version)
                self._graphs[key] = cached
        return cached

    def clear(self) -> None:
        with self._lock:
            self._graphs.clear()


GEO_V2_GRAPH_CACHE = GeoV2GraphCache()
