"""
Graph Reasoning Layer (lightweight — NOT a GNN, per project scope)
---------------------------------------------------------------------
Given a segment that Event Detection already flagged as anomalous, look
at its neighbors' recent behavior (vs THEIR OWN historical memory) and
raise/lower confidence based on whether they moved too. Real congestion
events typically show correlated movement on adjacent segments
(redistribution); a lone erratic segment with unaffected neighbors is
more likely sensor noise or a one-off, not a real road event.
"""
from dataclasses import dataclass

import networkx as nx

from app.services.road_graph.graph_builder import get_neighbors
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class NeighborSignal:
    segment_id: str
    deviation_score: float  # how far this neighbor is from ITS OWN baseline, 0..1+


@dataclass
class ReasoningResult:
    confidence_delta: float          # add this to the primary detector's confidence
    supporting_neighbors: list[str]  # neighbors whose behavior corroborates the event


def reason_over_neighbors(
    g: nx.DiGraph,
    flagged_segment_id: str,
    neighbor_deviation_lookup: dict[str, float],
) -> ReasoningResult:
    """
    `neighbor_deviation_lookup` : {segment_id: deviation_score}, expected
    to be produced by the same signature_extractor used on the flagged
    segment itself (see event_detection/signature_extractor.py) — this
    function does not compute deviations, only reasons over them, so it
    stays cheap to unit test.

    TODO: current logic is a simple threshold-and-average placeholder.
    Consider weighting by segment_length / road_type / historical
    correlation strength once you have enough labeled data to justify
    something fancier — the project brief explicitly scopes this as
    lightweight, not a GNN, so resist the urge to over-build it.
    """
    neighbor_ids = get_neighbors(g, flagged_segment_id, depth=settings.GRAPH_REASONING_NEIGHBOR_DEPTH)

    supporting = [
        n for n in neighbor_ids
        if neighbor_deviation_lookup.get(n, 0.0) > 0.3   # arbitrary starter threshold
    ]

    if not neighbor_ids:
        return ReasoningResult(confidence_delta=0.0, supporting_neighbors=[])

    corroboration_ratio = len(supporting) / len(neighbor_ids)
    # neighbors moving too => more confident; neighbors quiet => slightly less confident
    confidence_delta = (corroboration_ratio - 0.15) * 0.25

    logger.debug(
        "Segment %s: %d/%d neighbors corroborate -> confidence_delta=%.3f",
        flagged_segment_id, len(supporting), len(neighbor_ids), confidence_delta,
    )
    return ReasoningResult(confidence_delta=round(confidence_delta, 3), supporting_neighbors=supporting)
