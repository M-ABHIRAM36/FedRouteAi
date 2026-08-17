from datetime import datetime

from app.models.geo_v2 import GeoSegmentMetadata, GeoSegmentTransition, SegmentPrediction
from app.repositories.geo_v2_repository import GeoV2Repository
from app.services.geo_v2.network import normalize_overpass_json


def _network():
    return normalize_overpass_json({"elements": [{
        "type": "way", "id": 501, "nodes": [1, 2, 3],
        "geometry": [
            {"lat": 17.51, "lon": 78.29},
            {"lat": 17.512, "lon": 78.293},
            {"lat": 17.515, "lon": 78.291},
        ],
        "tags": {"highway": "secondary", "name": "Beeramguda Road", "lanes": "2"},
    }]})


def test_network_round_trip_preserves_geometry_and_is_idempotent(db_session):
    repository = GeoV2Repository(db_session)
    network = _network()

    for _ in range(2):
        repository.replace_network(
            network,
            network_version="beeramguda-test-v1",
            imported_at=datetime(2026, 8, 17),
        )

    restored = repository.load_network("beeramguda-test-v1")
    assert restored == network
    assert db_session.query(GeoSegmentMetadata).count() == len(network.segments)
    assert db_session.query(GeoSegmentTransition).count() == len(network.transitions)


def test_network_import_preserves_existing_v1_segments(db_session):
    from app.models.region import Region
    from app.models.segment import Segment

    db_session.add(Region(region_id="V1_REGION", pincode=500001, center_lat=17.4, center_lon=78.4))
    db_session.add(Segment(
        segment_id="HYD_SEG_0001", road_name="V1 Road", road_type="residential",
        region_id="V1_REGION", pincode=500001, start_lat=17.4, start_lon=78.4,
        end_lat=17.41, end_lon=78.41, segment_length_m=1000, number_of_lanes=2,
        road_width_m=7, max_speed_kmph=30, road_direction="bidirectional",
        flood_prone=False, neighbor_segments="",
    ))
    db_session.commit()

    GeoV2Repository(db_session).replace_network(
        _network(), network_version="beeramguda-test-v1", imported_at=datetime(2026, 8, 17)
    )

    assert db_session.get(Segment, "HYD_SEG_0001").road_name == "V1 Road"


def test_prediction_batch_is_idempotent(db_session):
    repository = GeoV2Repository(db_session)
    repository.replace_network(
        _network(), network_version="beeramguda-test-v1", imported_at=datetime(2026, 8, 17)
    )
    values = {
        "source_id": "geo-v2", "run_id": "run-1",
        "segment_id": _network().segments[0].segment_id,
        "timestamp": datetime(2026, 8, 17, 8), "predicted_label": None,
        "confidence": None, "class_probabilities": {}, "model_version": "untrained",
        "historical_baseline": {"avg_speed_kmph": 30},
        "current_deviation": {"speed_ratio": 1},
    }

    repository.save_predictions([values])
    repository.save_predictions([{**values, "predicted_label": "normal"}])

    assert db_session.query(SegmentPrediction).count() == 1
    assert db_session.query(SegmentPrediction).one().predicted_label == "normal"
