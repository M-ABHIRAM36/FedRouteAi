from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import torch

from app.ml.geo_v2.features import FEATURE_VARIANTS
from app.ml.geo_v2.dataset import LABEL_MAPPING
from app.ml.geo_v2.model import GeoV2MLP
from app.ml.geo_v2.model_store import DEFAULT_LABELS, GeoV2ModelStore, GeoV2Prediction
from app.models.geo_v2 import SegmentPrediction
from app.models.historical_memory import HistoricalMemory
from app.repositories.geo_v2_repository import GeoV2Repository
from app.schemas.geo_v2_inference import GeoV2InferenceItem
from app.services.geo_v2.prediction_service import GeoV2PredictionService
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.segment_repository import SegmentRepository
from app.services.geo_v2.runtime_inference import CausalFeatureContextCache
from app.services.geo_v2.network import normalize_overpass_json


def _artifact(path, *, version="geo-v2-test-1", feature_order=None):
    order = feature_order or FEATURE_VARIANTS["history_spatial"]
    torch.manual_seed(4)
    model = GeoV2MLP(len(order))
    torch.save({
        "model_state_dict": model.state_dict(), "feature_order": order,
        "scaler": {"mean": {name: 0.0 for name in order}, "scale": {name: 1.0 for name in order}},
        "label_mapping": {name: index for index, name in enumerate(DEFAULT_LABELS)},
        "model_version": version, "hidden_size": 64, "dropout_rate": 0.2,
    }, path)
    return model


def test_store_loads_once_returns_full_probabilities_and_matches_model(tmp_path, monkeypatch):
    path = tmp_path / "model.pt"
    model = _artifact(path)
    store = GeoV2ModelStore(path)
    loads = 0
    original = torch.load

    def counted(*args, **kwargs):
        nonlocal loads
        loads += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(torch, "load", counted)
    rows = np.arange(54, dtype=np.float32).reshape(2, 27) / 50
    first = store.predict(rows)
    second = store.predict(rows)
    expected = model.eval().predict_proba(torch.from_numpy(rows)).detach().numpy()

    assert loads == 1
    assert first.status == second.status == "ok"
    assert first.model_version == "geo-v2-test-1"
    assert len(first.probabilities) == 2
    assert tuple(first.probabilities[0]) == DEFAULT_LABELS
    assert sum(first.probabilities[0].values()) == pytest.approx(1.0)
    assert list(first.probabilities[0].values()) == pytest.approx(expected[0])


def test_store_reloads_new_version_and_rejects_schema_mismatch(tmp_path):
    path = tmp_path / "model.pt"
    _artifact(path, version="v1")
    store = GeoV2ModelStore(path)
    assert store.predict(np.zeros((1, 27), dtype=np.float32)).model_version == "v1"
    _artifact(path, version="v2")
    assert store.predict(np.zeros((1, 27), dtype=np.float32)).model_version == "v2"
    _artifact(path, feature_order=FEATURE_VARIANTS["history_spatial"][:-1])
    result = store.predict(np.zeros((1, 27), dtype=np.float32))
    assert result.status == "model_unavailable"
    assert result.probabilities is None


def test_missing_artifact_never_returns_a_label(tmp_path):
    result = GeoV2ModelStore(tmp_path / "missing.pt").predict(np.zeros((1, 27), dtype=np.float32))
    assert result.status == "model_unavailable"
    assert result.model_version is None
    assert result.probabilities is None


def test_store_accepts_existing_geo_v2_trainer_artifact():
    path = Path(__file__).resolve().parents[1] / "app/ml/artifacts/geo_v2/federated/practical-8r-2e-seed42/best_model.pt"
    if not path.exists():
        pytest.skip("existing trainer artifact is not present")
    result = GeoV2ModelStore(path).predict(np.zeros((1, 27), dtype=np.float32))

    assert result.status == "ok"
    assert result.model_version == "fedrouteai-geo-v2-round-08"
    assert tuple(result.probabilities[0]) == tuple(name for name, _ in sorted(LABEL_MAPPING.items(), key=lambda item: item[1]))


class _CountingStore:
    def __init__(self):
        self.calls = 0

    def predict(self, rows):
        self.calls += 1
        probabilities = [{name: (0.65 if name == "normal" else 0.05) for name in DEFAULT_LABELS} for _ in rows]
        return GeoV2Prediction("ok", "batch-model-v3", probabilities)


def _network():
    return normalize_overpass_json({"elements": [{
        "type": "way", "id": 900, "nodes": [1, 2, 3],
        "geometry": [{"lat": 17.5, "lon": 78.3}, {"lat": 17.501, "lon": 78.301}, {"lat": 17.502, "lon": 78.302}],
        "tags": {"highway": "primary", "lanes": "2", "maxspeed": "40"},
    }]})


def _seed(db_session):
    network = _network()
    GeoV2Repository(db_session).replace_network(network, network_version="runtime-test", imported_at=datetime(2026, 8, 17))
    for segment in network.segments:
        db_session.add(HistoricalMemory(
            segment_id=segment.segment_id, hour_of_day=8, avg_speed_kmph=30,
            std_speed_kmph=3, avg_vehicle_count=10, uturn_rate=0, sample_size=50,
        ))
    db_session.commit()
    return network


def _item(segment_id):
    return GeoV2InferenceItem.model_validate({
        "source_id": "runner", "run_id": "run-9", "segment_id": segment_id, "as_of": "2026-08-17T08:00:00",
        "telemetry": {"avg_speed_kmph": 20, "speed_std_kmph": 4, "vehicle_count": 14, "occupancy": 0.4, "flow_rate_vph": 80, "stopped_fraction": 0.1},
        "neighbors": [],
    })


def test_service_batches_one_model_call_and_persists_trace(db_session):
    network = _seed(db_session)
    store = _CountingStore()
    service = GeoV2PredictionService(
        SegmentRepository(db_session), HistoricalMemoryRepository(db_session), GeoV2Repository(db_session),
        store=store, cache=CausalFeatureContextCache(),
    )
    items = [_item(segment.segment_id) for segment in network.segments]
    results = service.infer_batch(items)

    assert store.calls == 1
    assert all(result.prediction == "normal" for _, _, result in results)
    assert all(result.model_version == "batch-model-v3" for _, _, result in results)
    rows = db_session.query(SegmentPrediction).all()
    assert len(rows) == len(items)
    assert rows[0].historical_baseline["feature_version"] == "geo-v2-history-spatial-27-v1"
    assert rows[0].current_deviation["speed_to_baseline"] == pytest.approx(2 / 3)
    assert rows[0].current_deviation["inference_status"] == "ok"


def test_service_bulk_history_is_causal_and_uses_three_prior_ticks(db_session):
    network = _seed(db_session)
    service = GeoV2PredictionService(
        SegmentRepository(db_session), HistoricalMemoryRepository(db_session), GeoV2Repository(db_session),
        store=_CountingStore(), cache=CausalFeatureContextCache(),
    )
    segment_id = network.segments[0].segment_id
    for minute, speed in enumerate((24, 21, 18, 15)):
        item = _item(segment_id).model_copy(update={
            "as_of": datetime(2026, 8, 17, 8, minute),
            "telemetry": _item(segment_id).telemetry.model_copy(update={"avg_speed_kmph": speed}),
        })
        service.infer_batch([item])

    final = _item(segment_id).model_copy(update={
        "as_of": datetime(2026, 8, 17, 8, 4),
        "telemetry": _item(segment_id).telemetry.model_copy(update={"avg_speed_kmph": 12}),
    })
    result = service.infer_batch([final])[0][2]

    assert result.deviations["prior_speed_mean_3"] == pytest.approx((21 + 18 + 15) / 3)
    assert result.deviations["speed_trend"] == pytest.approx(12 - (21 + 18 + 15) / 3)
    assert db_session.query(SegmentPrediction).filter_by(segment_id=segment_id).count() == 5


def test_api_missing_model_and_forbidden_labels(client, db_session, monkeypatch, tmp_path):
    # Seed through the TestClient's independent overridden session using the API dependency.
    from app.api.v1.endpoints import prediction as endpoint
    from app.db.session import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    network = _seed(db)
    monkeypatch.setattr(endpoint, "GEO_V2_MODEL_STORE", GeoV2ModelStore(tmp_path / "missing.pt"), raising=False)
    monkeypatch.setattr(
        endpoint, "_geo_v2_service",
        lambda session: GeoV2PredictionService(
            SegmentRepository(session), HistoricalMemoryRepository(session), GeoV2Repository(session),
            store=GeoV2ModelStore(tmp_path / "missing.pt"), cache=CausalFeatureContextCache(),
        ),
    )
    payload = _item(network.segments[0].segment_id).model_dump(mode="json")
    response = client.post("/api/v1/prediction/infer/geo-v2", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "model_unavailable"
    assert body["prediction"] is None and body["predicted_label"] is None
    assert body["probabilities"] == {}
    assert body["confidence_is_calibrated"] is False
    assert body["region"]

    payload["scenario"] = "construction"
    assert client.post("/api/v1/prediction/infer/geo-v2", json=payload).status_code == 422
    payload.pop("scenario")
    payload["label"] = "normal"
    assert client.post("/api/v1/prediction/infer/geo-v2", json=payload).status_code == 422


def test_batch_api_returns_single_inference_call_and_same_predictions(client, monkeypatch):
    from app.api.v1.endpoints import prediction as endpoint
    from app.db.session import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    network = _seed(db)
    store = _CountingStore()
    monkeypatch.setattr(
        endpoint, "_geo_v2_service",
        lambda session: GeoV2PredictionService(
            SegmentRepository(session), HistoricalMemoryRepository(session), GeoV2Repository(session),
            store=store, cache=CausalFeatureContextCache(),
        ),
    )
    items = [_item(segment.segment_id).model_dump(mode="json") for segment in network.segments]
    response = client.post("/api/v1/prediction/infer/batch", json={"items": items})
    body = response.json()

    assert response.status_code == 200
    assert store.calls == 1
    assert len(body["results"]) == len(items)
    assert {result["predicted_label"] for result in body["results"]} == {"normal"}
    assert {result["model_version"] for result in body["results"]} == {"batch-model-v3"}
