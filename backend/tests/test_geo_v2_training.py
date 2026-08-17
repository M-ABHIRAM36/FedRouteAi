from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from app.ml.geo_v2.dataset import LABEL_MAPPING
from app.ml.geo_v2.features import FEATURE_VARIANTS
from app.ml.geo_v2.training import (
    EXPECTED_REGIONS, ArrayDataset, GeoV2EventClassifierMLP, RegionalClient,
    TrainingConfig, aggregate_client_updates, build_regional_clients,
    load_geo_v2_artifact, load_ndarrays_into_model, read_canonical_split,
    save_model_artifact, select_best_validation_checkpoint,
    state_dict_to_ndarrays, validate_scaler_and_schema,
)
from app.ml.training.adaptive_fedavg import AdaptiveFedAvg


def _dataset(rows_per_region: int = 8) -> ArrayDataset:
    regions = tuple(region for region in EXPECTED_REGIONS for _ in range(rows_per_region))
    labels = np.tile(np.arange(8), len(regions) // 8)
    return ArrayDataset(
        np.arange(len(regions) * 27, dtype=np.float32).reshape(len(regions), 27) / 100,
        labels.astype(np.int64), tuple(f"row-{index}" for index in range(len(regions))), regions,
    )


def test_parameter_roundtrip_includes_batchnorm_buffers():
    model = GeoV2EventClassifierMLP(27, hidden_size=16)
    model.train()
    model(torch.randn(4, 27))
    arrays = state_dict_to_ndarrays(model)
    restored = GeoV2EventClassifierMLP(27, hidden_size=16)
    load_ndarrays_into_model(restored, arrays)
    assert list(model.state_dict()) == list(restored.state_dict())
    assert any("running_mean" in name for name in model.state_dict())
    assert any("num_batches_tracked" in name for name in model.state_dict())
    for name in model.state_dict():
        torch.testing.assert_close(model.state_dict()[name], restored.state_dict()[name])


def test_scaler_and_schema_validation_rejects_wrong_order_and_forbidden_fields():
    schema = {"variants": FEATURE_VARIANTS}
    features = FEATURE_VARIANTS["history_spatial"]
    scaler = {"fit_split": "train", "feature_order": features, "mean": {name: 0.0 for name in features}, "scale": {name: 1.0 for name in features}}
    assert validate_scaler_and_schema(schema, scaler) == tuple(features)
    invalid = json.loads(json.dumps(scaler))
    invalid["feature_order"] = list(reversed(features))
    with pytest.raises(ValueError, match="feature order"):
        validate_scaler_and_schema(schema, invalid)
    forbidden_schema = {"variants": {**FEATURE_VARIANTS, "history_spatial": [*features[:-1], "event_id"]}}
    with pytest.raises(ValueError):
        validate_scaler_and_schema(forbidden_schema, scaler)


def test_downsample_applies_only_to_training_normals(tmp_path: Path):
    features = FEATURE_VARIANTS["history_spatial"]
    rows = []
    for region in EXPECTED_REGIONS:
        for label, label_idx in LABEL_MAPPING.items():
            rows.append({"row_id": f"{region}-{label}", "split": "train", "region_id": region, **{name: 0.0 for name in features}, "label": label, "label_idx": label_idx})
        for index in range(4):
            rows.append({"row_id": f"{region}-normal-extra-{index}", "split": "train", "region_id": region, **{name: 0.0 for name in features}, "label": "normal", "label_idx": 0})
    path = tmp_path / "train.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    sampled, record = read_canonical_split(path, "train", features, normal_cap=8, seed=9, chunk_size=13)
    assert (sampled.label_idx != 0).sum() == 7 * 8
    assert (sampled.label_idx == 0).sum() == 8
    assert record["retained_event_rows"] == record["original_event_rows"]
    full, full_record = read_canonical_split(path, "train", features, normal_cap=None, seed=9, chunk_size=13)
    assert len(full) == len(rows)
    assert full_record["retained_normal_rows"] == full_record["original_normal_rows"]


def test_eight_client_uniqueness_is_required():
    data = _dataset()
    clients = build_regional_clients(data, data)
    assert tuple(clients) == EXPECTED_REGIONS
    invalid = dict(clients)
    invalid.pop("REGION_08")
    arrays = state_dict_to_ndarrays(GeoV2EventClassifierMLP(27))
    strategy = AdaptiveFedAvg(global_class_frequencies={index: 0.125 for index in range(8)})
    updates = [(region, arrays, len(client.train), {"region_id": region}) for region, client in invalid.items()]
    with pytest.raises(ValueError, match="exactly 8 unique"):
        aggregate_client_updates(strategy, 1, updates)


def test_adaptive_aggregation_is_called_and_weights_sum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    model = GeoV2EventClassifierMLP(27)
    arrays = state_dict_to_ndarrays(model)
    strategy = AdaptiveFedAvg(
        global_class_frequencies={index: 0.125 for index in range(8)},
        weight_log_path=tmp_path / "weights.csv",
    )
    original = strategy.aggregate_fit
    called = {"count": 0}
    def spy(*args, **kwargs):
        called["count"] += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(strategy, "aggregate_fit", spy)
    updates = [(region, arrays, 10, {"region_id": region, "val_macro_f1": 0.5, "rare_class_fraction": 0.2}) for region in EXPECTED_REGIONS]
    result = aggregate_client_updates(strategy, 1, updates)
    assert called["count"] == 1
    assert len(result) == len(arrays)
    weights = pd.read_csv(tmp_path / "weights.csv")
    assert weights.region_id.nunique() == 8
    assert weights.normalized_weight.sum() == pytest.approx(1.0)


def test_checkpoint_selection_uses_validation_only():
    history = [
        {"checkpoint_index": 1, "validation_macro_f1": 0.4, "test_macro_f1": 0.99},
        {"checkpoint_index": 2, "validation_macro_f1": 0.8, "test_macro_f1": 0.01},
    ]
    assert select_best_validation_checkpoint(history) == 2
    with pytest.raises(ValueError, match="validation_macro_f1"):
        select_best_validation_checkpoint([{"checkpoint_index": 1, "test_macro_f1": 1.0}])


def test_artifact_load_probability_parity(tmp_path: Path):
    model = GeoV2EventClassifierMLP(27, hidden_size=16)
    model.eval()
    features = torch.randn(5, 27)
    expected = model.predict_proba(features)
    names = FEATURE_VARIANTS["history_spatial"]
    scaler = {"fit_split": "train", "mean": {name: float(index) for index, name in enumerate(names)}, "scale": {name: 1.0 for name in names}}
    manifest = {"dataset_version": "geo_v2_ml_v1", "network_version": "test-network"}
    path = tmp_path / "model.pt"
    save_model_artifact(path, model, scaler, manifest, TrainingConfig(hidden_size=16), tmp_path, round_number=3, checkpoint_metric=0.5)
    loaded, artifact = load_geo_v2_artifact(path)
    torch.testing.assert_close(expected, loaded.predict_proba(features))
    assert artifact["model_version"] == "fedrouteai-geo-v2-round-03"
    assert artifact["ordered_feature_names"] == names
