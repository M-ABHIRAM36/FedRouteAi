"""
Adaptive Federated Aggregation
----------------------------------
Extends Flower's FedAvg to weight each region's contribution by the
five factors named in the project brief, all computed for real (not
placeholders) from what a client reports plus this region's own FL
round history (app/models/fl_round_record.py):

  data_quality       : client-reported, currently sample-volume-based
                        (see flower_client.py)
  event_confidence    : average confidence of this region's recently
                        DETECTED events — noisy regions get downweighted
  historical_similarity : cosine similarity between this round's fitted
                        mean vector and THIS SAME region's own previous
                        round — measures consistency, not agreement with
                        other regions (a region can legitimately have
                        different-but-consistent local traffic patterns)
  temporal_recency    : decays if the region's training data is stale
  regional_relevance  : normalized by segment_count relative to the
                        largest region participating this round

Every factor defaults to "no penalty" (1.0-ish) when its supporting data
doesn't exist yet (e.g. first round ever for a region) — the point is
to differentiate once history exists, not to punish cold starts.
"""
import math
from datetime import datetime

from app.utils.time_utils import utcnow
from typing import List, Tuple, Optional

import numpy as np
import flwr as fl
from flwr.common import FitRes, Parameters, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy

from app.db.session import SessionLocal
from app.repositories.fl_round_repository import FLRoundRepository
from app.repositories.event_repository import EventRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _historical_similarity_factor(current_mean: np.ndarray, previous_mean_csv: str | None) -> float:
    if not previous_mean_csv:
        return 1.0
    previous_mean = np.array([float(x) for x in previous_mean_csv.split(",")])
    if previous_mean.shape != current_mean.shape:
        return 1.0
    denom = (np.linalg.norm(current_mean) * np.linalg.norm(previous_mean)) or 1e-9
    cos_sim = float(np.dot(current_mean, previous_mean) / denom)
    return 0.5 + 0.5 * max(-1.0, min(1.0, cos_sim))  # maps [-1,1] -> [0,1], never fully zeroes a region out


def _temporal_recency_factor(data_timestamp_iso: str | None, now: datetime) -> float:
    if not data_timestamp_iso:
        return 1.0
    try:
        data_time = datetime.fromisoformat(data_timestamp_iso)
    except ValueError:
        return 1.0
    hours_stale = max(0.0, (now - data_time).total_seconds() / 3600)
    return max(0.3, 1 - hours_stale / 72)  # linear decay to a 0.3 floor over 3 days


def _event_confidence_factor(region_id: str, db) -> float:
    events = EventRepository(db).get_active_all()
    region_events = [e for e in events if e.region_id == region_id]
    if not region_events:
        return 1.0
    return float(np.mean([e.confidence for e in region_events]))


class AdaptiveFedAvg(fl.server.strategy.FedAvg):
    def __init__(self, *args, session_factory=SessionLocal, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_factory = session_factory

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures,
    ) -> Tuple[Optional[Parameters], dict]:
        if not results:
            return None, {}

        db = self.session_factory()
        round_repo = FLRoundRepository(db)
        now = utcnow()

        try:
            segment_counts = [r.metrics.get("regional_relevance_raw", 1.0) for _, r in results]
            max_segment_count = max(segment_counts) or 1.0

            weighted_arrays = None
            total_weight = 0.0

            for _, fit_res in results:
                arrays = parameters_to_ndarrays(fit_res.parameters)
                current_mean = arrays[0]
                region_id = fit_res.metrics.get("region_id", "UNKNOWN")

                data_quality = fit_res.metrics.get("data_quality_score", 1.0)
                event_confidence = _event_confidence_factor(region_id, db)

                previous_round = round_repo.get_latest_for_region(region_id)
                historical_similarity = _historical_similarity_factor(
                    current_mean, previous_round.mean_vector_csv if previous_round else None
                )
                temporal_recency = _temporal_recency_factor(fit_res.metrics.get("data_timestamp"), now)
                regional_relevance = fit_res.metrics.get("regional_relevance_raw", 1.0) / max_segment_count

                weight = (
                    fit_res.num_examples
                    * data_quality
                    * event_confidence
                    * historical_similarity
                    * temporal_recency
                    * regional_relevance
                )

                logger.info(
                    "Round %d | %s: quality=%.2f event_conf=%.2f hist_sim=%.2f recency=%.2f "
                    "relevance=%.2f -> weight=%.2f",
                    server_round, region_id, data_quality, event_confidence,
                    historical_similarity, temporal_recency, regional_relevance, weight,
                )

                round_repo.record_round(
                    region_id=region_id, round_number=server_round,
                    data_quality_score=data_quality, local_loss=fit_res.metrics.get("local_loss", 0.0),
                    num_samples=fit_res.num_examples,
                    mean_vector_csv=",".join(str(x) for x in current_mean.tolist()),
                    data_timestamp=datetime.fromisoformat(fit_res.metrics["data_timestamp"])
                        if fit_res.metrics.get("data_timestamp") else now,
                    submitted_at=now,
                )

                if weighted_arrays is None:
                    weighted_arrays = [w * weight for w in arrays]
                else:
                    weighted_arrays = [acc + w * weight for acc, w in zip(weighted_arrays, arrays)]
                total_weight += weight

            if total_weight == 0:
                logger.warning("Round %d: total_weight was 0, falling back to equal weighting", server_round)
                total_weight = len(results)
                weighted_arrays = [sum(parameters_to_ndarrays(r.parameters)[i] for _, r in results) for i in range(len(arrays))]

            aggregated = [w / total_weight for w in weighted_arrays]
            logger.info("Round %d: aggregated %d client updates (total_weight=%.2f)", server_round, len(results), total_weight)
            return ndarrays_to_parameters(aggregated), {}
        finally:
            db.close()
