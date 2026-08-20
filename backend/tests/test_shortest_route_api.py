from datetime import datetime

from app.repositories.geo_v2_repository import GeoV2Repository
from tests.test_shortest_route import NETWORK_SOURCE, NETWORK_VERSION, _network


def test_shortest_route_api_returns_route_and_validates_requests(client, monkeypatch):
    from app.main import app
    from app.db.session import get_db

    dependency = app.dependency_overrides[get_db]
    db = next(dependency())
    try:
        GeoV2Repository(db).replace_network(
            _network(), network_source=NETWORK_SOURCE, network_version=NETWORK_VERSION,
            imported_at=datetime(2026, 8, 21),
        )
    finally:
        db.close()

    payload = {
        "origin": {"lat": 17.5100, "lon": 78.2900},
        "destination": {"lat": 17.5100, "lon": 78.2940},
        "network_source": NETWORK_SOURCE,
        "network_version": NETWORK_VERSION,
    }
    response = client.post("/api/v1/routes/shortest", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == "Dijkstra"
    assert body["cost_basis"] == "distance"
    assert body["ordered_segment_ids"] == ["ROUTE_A", "ROUTE_B", "ROUTE_C"]
    assert body["geometry"]["type"] == "LineString"
    assert body["segment_count"] == 3
    assert body["computation_time_ms"] >= 0

    malformed = client.post("/api/v1/routes/shortest", json={"origin": {"lat": 100, "lon": 0}})
    assert malformed.status_code == 422

    same = client.post("/api/v1/routes/shortest", json={
        **payload, "destination": payload["origin"],
    })
    assert same.status_code == 422


def test_shortest_route_api_reports_missing_network(client):
    response = client.post("/api/v1/routes/shortest", json={
        "origin": {"lat": 17.5100, "lon": 78.2900},
        "destination": {"lat": 17.5100, "lon": 78.2940},
        "network_source": NETWORK_SOURCE,
        "network_version": "missing-network",
    })
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]
