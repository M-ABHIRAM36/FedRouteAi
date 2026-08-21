from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.geo_v2.robust_training import (
    RobustTrainingConfig, classification_metrics, sample_client_aware,
    bounded_weights, hierarchy_dominates_flat, selection_key,
)
from app.ml.geo_v2.training import EXPECTED_REGIONS


def _frame() -> pd.DataFrame:
    rows = []
    for region in EXPECTED_REGIONS:
        for index in range(3):
            rows.append({"row_id": f"{region}-event-{index}", "region_id": region, "label_idx": index + 1})
        for index in range(300):
            rows.append({"row_id": f"{region}-normal-{index}", "region_id": region, "label_idx": 0})
    return pd.DataFrame(rows)


def test_client_aware_sampling_is_deterministic_geographic_and_never_duplicates_events():
    frame = _frame()
    first, record = sample_client_aware(frame, target_anomaly_fraction=0.02, seed=42)
    second, _ = sample_client_aware(frame, target_anomaly_fraction=0.02, seed=42)

    assert first.row_id.tolist() == second.row_id.tolist()
    assert not first.row_id.duplicated().any()
    assert set(first.loc[first.label_idx != 0, "row_id"]) == set(frame.loc[frame.label_idx != 0, "row_id"])
    assert record["event_duplication"] is False
    assert record["geographic_rows_moved"] is False
    for region, values in record["clients"].items():
        assert values["event_rows"] == 3
        assert values["normal_rows"] == 147
        assert values["event_fraction"] == pytest.approx(0.02)
        assert set(first.loc[first.region_id == region, "region_id"]) == {region}


def test_metrics_expose_normal_false_positives_and_anomaly_recall():
    labels = np.array([0, 0, 0, 1, 2])
    predictions = np.array([0, 1, 0, 1, 0])
    probabilities = np.eye(8, dtype=np.float32)[predictions]
    metrics = classification_metrics(labels, probabilities)

    assert metrics["normal"]["false_positives"] == 1
    assert metrics["normal"]["false_positive_rate"] == pytest.approx(1 / 3)
    assert metrics["normal"]["false_positives_per_100000"] == pytest.approx(100_000 / 3)
    assert metrics["anomaly"]["precision"] == pytest.approx(0.5)
    assert metrics["anomaly"]["recall"] == pytest.approx(0.5)


def test_selection_rejects_normal_only_and_event_heavy_models():
    normal_only = {
        "selection_eligible": False,
        "deployment": {"normal": {"false_positive_rate": 0.0}},
        "event_balanced": {"macro_f1": 0.12},
    }
    event_heavy = {
        "selection_eligible": False,
        "deployment": {"normal": {"false_positive_rate": 0.60}},
        "event_balanced": {"macro_f1": 0.40},
    }
    accepted = {
        "selection_eligible": True,
        "deployment": {"macro_f1": 0.30, "anomaly": {"recall": 0.50}, "normal": {"specificity": 0.98, "false_positive_rate": 0.02}},
        "event_balanced": {"macro_f1": 0.45},
    }

    assert selection_key(accepted) > selection_key(normal_only)
    assert selection_key(accepted) > selection_key(event_heavy)


def test_robust_config_rejects_invalid_experiment_values():
    with pytest.raises(ValueError):
        RobustTrainingConfig(target_local_anomaly_fraction=0.7).validate()
    with pytest.raises(ValueError):
        RobustTrainingConfig(rounds=0).validate()


def test_adaptive_weight_projection_preserves_sum_and_client_bounds():
    projected = bounded_weights([1, 2, 3, 4, 5, 6, 7, 100], 0.03, 0.22)
    assert projected.sum() == pytest.approx(1.0)
    assert projected.min() >= 0.03
    assert projected.max() <= 0.22
    assert projected[-1] == pytest.approx(0.22)


def test_hierarchy_must_not_trade_away_declared_secondary_objectives():
    flat = {
        "selection_eligible": True,
        "deployment": {"macro_f1": 0.30, "anomaly": {"recall": 0.36}},
        "event_balanced": {"macro_f1": 0.42},
    }
    higher_primary_lower_recall = {
        "selection_eligible": True,
        "deployment": {"macro_f1": 0.31, "anomaly": {"recall": 0.30}},
        "event_balanced": {"macro_f1": 0.43},
    }
    dominating = {
        "selection_eligible": True,
        "deployment": {"macro_f1": 0.31, "anomaly": {"recall": 0.36}},
        "event_balanced": {"macro_f1": 0.43},
    }
    assert not hierarchy_dominates_flat(higher_primary_lower_recall, flat)
    assert hierarchy_dominates_flat(dominating, flat)
