"""
Flower Client (one per region)
----------------------------------
Loads REAL training data via the repository layer: pulls this region's
segments, gets each one's recent pings + historical baseline, extracts
a behavioral signature per segment (same function the live detector
uses), and trains the local Gaussian model on those signature vectors.

Falls back to a small amount of synthetic noise around 1.0 ONLY when a
region genuinely has no baseline/pings yet (cold start, e.g. right
after `seed_db.py` before any historical memory has been built) — this
keeps the FL round runnable end-to-end during initial setup without
silently pretending there's real signal when there isn't.
"""
from datetime import timedelta

from app.utils.time_utils import utcnow

import numpy as np
import flwr as fl

from app.db.session import SessionLocal
from app.repositories.segment_repository import SegmentRepository
from app.repositories.gps_repository import GPSPingRepository
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.region_repository import RegionRepository
from app.services.event_detection.signature_extractor import extract_signature
from app.services.federated_learning.local_model import LocalModel, N_FEATURES
from app.core.logging_config import get_logger

logger = get_logger(__name__)

TRAINING_LOOKBACK_HOURS = 6


def load_region_training_data(region_id: str) -> tuple[np.ndarray, bool]:
    """Returns (X, used_real_data). X has shape (n_samples, N_FEATURES)."""
    db = SessionLocal()
    try:
        segment_repo, gps_repo, memory_repo = SegmentRepository(db), GPSPingRepository(db), HistoricalMemoryRepository(db)
        segments = segment_repo.get_by_region(region_id)
        since = utcnow() - timedelta(hours=TRAINING_LOOKBACK_HOURS)

        rows = []
        for seg in segments:
            baseline = memory_repo.get_baseline(seg.segment_id, utcnow().hour)
            if baseline is None:
                continue
            pings = gps_repo.get_recent_for_segment(seg.segment_id, since)
            sig = extract_signature(pings, baseline)
            if sig is not None:
                rows.append([sig.speed_ratio, sig.density_ratio, sig.uturn_ratio, sig.variance_ratio])

        if len(rows) >= 10:
            return np.array(rows, dtype=np.float32), True

        logger.warning("Region %s: only %d real signature samples available, padding with cold-start noise", region_id, len(rows))
        rng = np.random.default_rng(hash(region_id) % (2**32))
        padding = rng.normal(loc=1.0, scale=0.15, size=(max(50 - len(rows), 10), N_FEATURES)).astype(np.float32)
        X = np.vstack([np.array(rows, dtype=np.float32), padding]) if rows else padding
        return X, False
    finally:
        db.close()


def get_region_segment_count(region_id: str) -> float:
    db = SessionLocal()
    try:
        region = RegionRepository(db).get(region_id)
        return float(region.segment_count) if region else 1.0
    finally:
        db.close()


class FedRouteAIClient(fl.client.NumPyClient):
    def __init__(self, region_id: str):
        self.region_id = region_id
        self.model = LocalModel.initial()

    def get_parameters(self, config):
        return self.model.get_parameters()

    def fit(self, parameters, config):
        self.model.set_parameters(parameters)
        X, used_real_data = load_region_training_data(self.region_id)
        loss = self.model.fit(X)

        metrics = {
            "region_id": self.region_id,
            "data_quality_score": min(1.0, len(X) / 200) * (1.0 if used_real_data else 0.5),
            "local_loss": loss,
            "data_timestamp": utcnow().isoformat(),
            "regional_relevance_raw": get_region_segment_count(self.region_id),
        }
        return self.model.get_parameters(), len(X), metrics

    def evaluate(self, parameters, config):
        self.model.set_parameters(parameters)
        X, _ = load_region_training_data(self.region_id)
        z = (X - self.model.mean) / self.model.std
        loss = float(np.mean(0.5 * z ** 2))
        return loss, len(X), {"region_id": self.region_id}


def start_client(region_id: str, server_address: str = "127.0.0.1:8080"):
    logger.info("Starting Flower client for %s -> %s", region_id, server_address)
    fl.client.start_client(
        server_address=server_address,
        client=FedRouteAIClient(region_id).to_client(),
    )
