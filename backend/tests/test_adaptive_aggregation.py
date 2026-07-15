import numpy as np

from app.services.federated_learning.adaptive_aggregation import (
    _historical_similarity_factor,
    _temporal_recency_factor,
)
from app.utils.time_utils import utcnow


def test_historical_similarity_no_previous_round_defaults_to_full_trust():
    factor = _historical_similarity_factor(np.array([1.0, 1.0, 1.0, 1.0]), previous_mean_csv=None)
    assert factor == 1.0


def test_historical_similarity_identical_vectors_scores_high():
    current = np.array([1.0, 0.9, 1.1, 1.0])
    previous_csv = "1.0,0.9,1.1,1.0"
    factor = _historical_similarity_factor(current, previous_csv)
    assert factor > 0.95


def test_historical_similarity_divergent_vectors_scores_lower():
    current = np.array([1.0, 0.9, 1.1, 1.0])
    previous_csv = "-1.0,-0.9,-1.1,-1.0"  # opposite direction
    factor = _historical_similarity_factor(current, previous_csv)
    assert factor < 0.1


def test_temporal_recency_fresh_data_scores_near_one():
    factor = _temporal_recency_factor(utcnow().isoformat(), utcnow())
    assert factor > 0.95


def test_temporal_recency_stale_data_decays():
    from datetime import timedelta
    now = utcnow()
    stale_timestamp = (now - timedelta(hours=48)).isoformat()
    factor = _temporal_recency_factor(stale_timestamp, now)
    assert 0.3 <= factor < 0.7  # decayed but not below the floor


def test_temporal_recency_missing_timestamp_defaults_to_full_trust():
    assert _temporal_recency_factor(None, utcnow()) == 1.0
