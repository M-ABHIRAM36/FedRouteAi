"""Admin/observability schemas for the federated learning subsystem —
NOT used by clients to send raw data (they never should)."""
from datetime import datetime

from pydantic import BaseModel


class ClientRoundSummary(BaseModel):
    region_id: str
    round_number: int
    data_quality_score: float
    local_loss: float
    num_samples: int
    submitted_at: datetime


class GlobalModelStatus(BaseModel):
    round_number: int
    participating_regions: list[str]
    aggregated_at: datetime
    global_val_loss: float | None = None
