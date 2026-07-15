"""Read-only observability into the FL subsystem — NOT where raw data
flows (that never leaves each region's own client process)."""
from fastapi import APIRouter
from datetime import datetime, timezone

from app.services.federated_learning.global_model import GLOBAL_MODEL_STORE
from app.schemas.federated import GlobalModelStatus

router = APIRouter(prefix="/federated", tags=["federated"])


@router.get("/status", response_model=GlobalModelStatus)
def global_model_status():
    return GlobalModelStatus(
        round_number=GLOBAL_MODEL_STORE.round_number,
        participating_regions=[],  # TODO: track per-round participant list in GlobalModelStore
        aggregated_at=datetime.now(timezone.utc),
    )
