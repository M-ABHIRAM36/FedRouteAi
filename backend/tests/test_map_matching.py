from types import SimpleNamespace

from app.services.map_matching.matcher import match_point, match_trajectory


def _seg(seg_id, lat1, lon1, lat2, lon2, neighbors=""):
    return SimpleNamespace(segment_id=seg_id, start_lat=lat1, start_lon=lon1, end_lat=lat2, end_lon=lon2,
                            neighbor_segments=neighbors)


def test_match_point_picks_nearest_segment():
    segments = [
        _seg("A", 17.3850, 78.4867, 17.3860, 78.4867),   # runs north
        _seg("B", 17.3850, 78.5000, 17.3860, 78.5000),   # far away
    ]
    # a point right on segment A's line
    result = match_point(17.3855, 78.4867, segments)
    assert result.segment_id == "A"
    assert result.confidence > 0.9


def test_match_point_no_confident_match_returns_none():
    segments = [_seg("A", 17.3850, 78.4867, 17.3860, 78.4867)]
    # a point far from any candidate
    result = match_point(17.5000, 78.7000, segments)
    assert result.segment_id is None
    assert result.confidence == 0.0


def test_trajectory_continuity_prefers_connected_segment_on_near_tie():
    """Two roads ~12m apart at the same latitude range. A point sits
    marginally closer to the unrelated PARALLEL road (5.5m) than to
    MAIN_CONT (6.5m) — close enough that real GPS noise could easily
    produce this. Continuity should still pull the match toward
    MAIN_CONT once the vehicle's previous match was MAIN, since
    MAIN_CONT is the one actually connected to it."""
    main_road = _seg("MAIN", 17.3850, 78.4867, 17.3860, 78.4867, neighbors="MAIN_CONT")
    continuation = _seg("MAIN_CONT", 17.3860, 78.4867, 17.3870, 78.4867, neighbors="MAIN")
    # verified via geo_utils.offset_latlon: exactly 12m east of the continuation
    parallel_road = _seg("PARALLEL", 17.386, 78.48681295801195, 17.387, 78.48681295862927)

    segments = [continuation, parallel_road]
    # verified distances: 6.5m to MAIN_CONT, 5.5m to PARALLEL
    test_point = (17.3861, 78.48676118562325)

    result_no_context = match_point(*test_point, segments, previous_segment_id=None)
    result_with_context = match_point(*test_point, segments, previous_segment_id="MAIN")

    # with no trajectory context, the nearer point wins outright
    assert result_no_context.segment_id == "PARALLEL"
    # with continuity from having just been on MAIN, the connected
    # segment wins the near-tie instead
    assert result_with_context.segment_id == "MAIN_CONT"


def test_match_trajectory_carries_previous_match_forward():
    main_road = _seg("MAIN", 17.3850, 78.4867, 17.3860, 78.4867, neighbors="MAIN_CONT")
    continuation = _seg("MAIN_CONT", 17.3860, 78.4867, 17.3870, 78.4867, neighbors="MAIN")
    segments = [main_road, continuation]

    points = [(17.3855, 78.4867), (17.3865, 78.4867)]
    results = match_trajectory(points, segments)

    assert results[0].segment_id == "MAIN"
    assert results[1].segment_id == "MAIN_CONT"
