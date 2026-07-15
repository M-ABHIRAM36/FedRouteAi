"""
Map Matching Service
---------------------
Converts raw (lat, lon) GPS into the segment_id it actually belongs to.
Two things make this a real matcher rather than "just find the closest
line": (1) proper point-to-segment perpendicular projection instead of
sampling a few points along the line, and (2) trajectory continuity —
a point's previous match is used to prefer segments connected to it,
which is what actually disambiguates parallel roads and intersections
(the classic map-matching failure mode).

No external service (FMM/OSRM) required — this stays a good-enough
in-process matcher for Phase 1. If you outgrow it (very noisy real GPS,
dense multi-lane roads), swap in FMM; the call signature here is
designed so that swap only touches this file.
"""
from dataclasses import dataclass

from app.models.segment import Segment
from app.utils.geo_utils import haversine_m, meters_per_deg_lon, METERS_PER_DEG_LAT
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MatchResult:
    segment_id: str | None
    distance_m: float
    confidence: float


def _project_point_to_segment_m(lat: float, lon: float, seg: Segment) -> float:
    """Real point-to-line-segment distance, done in a local flat-meter
    frame (accurate for segment-scale distances, i.e. tens-hundreds of
    meters — see geo_utils docstring for why lat/lon degrees aren't
    interchangeable and must be converted through the same origin)."""
    origin_lat = seg.start_lat
    mlat = METERS_PER_DEG_LAT
    mlon = meters_per_deg_lon(origin_lat)

    def to_xy(lat_, lon_):
        return (lon_ - seg.start_lon) * mlon, (lat_ - origin_lat) * mlat

    ax, ay = 0.0, 0.0
    bx, by = to_xy(seg.end_lat, seg.end_lon)
    px, py = to_xy(lat, lon)

    abx, aby = bx - ax, by - ay
    seg_len_sq = abx ** 2 + aby ** 2
    if seg_len_sq < 1e-9:
        return haversine_m(lat, lon, seg.start_lat, seg.start_lon)

    t = ((px - ax) * abx + (py - ay) * aby) / seg_len_sq
    t = max(0.0, min(1.0, t))  # clamp to the segment, not the infinite line

    cx, cy = ax + t * abx, ay + t * aby
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def match_point(
    lat: float,
    lon: float,
    candidate_segments: list[Segment],
    previous_segment_id: str | None = None,
) -> MatchResult:
    """Match one point. If `previous_segment_id` is given and is itself
    (or a neighbor of) one of the candidates, that candidate gets a
    distance discount — this is the trajectory-continuity heuristic that
    keeps a moving vehicle from flickering between two nearby parallel
    roads."""
    scored: list[tuple[Segment, float]] = []
    for seg in candidate_segments:
        d = _project_point_to_segment_m(lat, lon, seg)
        scored.append((seg, d))

    if not scored:
        return MatchResult(segment_id=None, distance_m=float("inf"), confidence=0.0)

    if previous_segment_id is not None:
        continuity_bonus_m = 8.0  # small, deliberate: nudges ties, doesn't override real distance
        adjusted = []
        for seg, d in scored:
            is_continuation = seg.segment_id == previous_segment_id or (
                previous_segment_id in (seg.neighbor_segments or "").split(";")
            )
            adjusted.append((seg, d - continuity_bonus_m if is_continuation else d))
        scored = adjusted

    best_seg, best_dist_adjusted = min(scored, key=lambda pair: pair[1])
    # report the TRUE (unadjusted) distance for confidence, not the continuity-biased one
    true_dist = next(d for seg, d in [(s, _project_point_to_segment_m(lat, lon, s)) for s in candidate_segments]
                      if seg.segment_id == best_seg.segment_id)

    if true_dist > settings.MAP_MATCH_MAX_CANDIDATE_DISTANCE_M:
        logger.debug("No confident match for (%.5f, %.5f); best_dist=%.1fm", lat, lon, true_dist)
        return MatchResult(segment_id=None, distance_m=true_dist, confidence=0.0)

    confidence = max(0.0, 1 - true_dist / settings.MAP_MATCH_MAX_CANDIDATE_DISTANCE_M)
    return MatchResult(segment_id=best_seg.segment_id, distance_m=round(true_dist, 2), confidence=round(confidence, 3))


def match_trajectory(points: list[tuple[float, float]], candidate_segments: list[Segment]) -> list[MatchResult]:
    """Match an ordered trajectory, carrying the previous match forward
    so continuity actually kicks in (a single match_point call has no
    'previous' to use — this is the function that makes it matter)."""
    results: list[MatchResult] = []
    previous_id: str | None = None
    for lat, lon in points:
        result = match_point(lat, lon, candidate_segments, previous_segment_id=previous_id)
        results.append(result)
        if result.segment_id is not None:
            previous_id = result.segment_id
    return results
