"""
Graph cache — builds the NetworkX segment graph once (at app startup)
instead of on every /routes request. Structure (which segments connect
to which) barely changes at runtime; only edge WEIGHTS change when
events start/end, and cost_model.apply_event_penalties() already
returns a repriced copy without needing to touch the DB again — so
caching the structure and repricing per-request is the right split.

Invalidate (call `refresh()`) if segments themselves are ever added/
removed at runtime — Phase 1 doesn't do that, so this is a manual hook
for later rather than something wired to a change-event today.
"""
import networkx as nx
from sqlalchemy.orm import Session

from app.repositories.segment_repository import SegmentRepository
from app.services.road_graph.graph_builder import build_segment_graph
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GraphCache:
    def __init__(self):
        self._graph: nx.DiGraph | None = None

    def get(self, db: Session) -> nx.DiGraph:
        if self._graph is None:
            self.refresh(db)
        return self._graph

    def refresh(self, db: Session) -> nx.DiGraph:
        segments = SegmentRepository(db).list_all(limit=100_000)
        self._graph = build_segment_graph(segments)
        logger.info("Graph cache (re)built: %d nodes, %d edges", self._graph.number_of_nodes(), self._graph.number_of_edges())
        return self._graph


# process-wide singleton — fine for Phase 1's single-process deployment;
# if you scale to multiple API workers, each gets its own copy (cheap to
# rebuild, no shared-state bug, just not memory-optimal at scale)
GRAPH_CACHE = GraphCache()
