import time
import torch
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.segment import Segment
from app.models.historical_memory import HistoricalMemory
from app.schemas.predict import PredictionRequest, PredictionResponse
from app.services.federated_learning.local_model import MLPLocalModel, IDX_TO_LABEL
from app.ml.features.windowing import ROAD_TYPE_ORDINAL

router = APIRouter(prefix="/predict", tags=["predict"])

# Global state for loaded model
_MODEL = None
_MODEL_PATH = Path(__file__).resolve().parents[5] / "app" / "ml" / "artifacts" / "adaptive_federated" / "best_global_model.pt"

def get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
        
    if not _MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail="Trained global model (best_global_model.pt) not found.")
        
    # Instantiate the empty model and load the weights
    model = MLPLocalModel()
    try:
        model.net.load_state_dict(torch.load(_MODEL_PATH, map_location=torch.device("cpu")))
        model.net.eval()
        _MODEL = model
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")
        
    return _MODEL

@router.post("", response_model=PredictionResponse)
def predict_road_event(request: PredictionRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    
    # 1. Fetch Segment and Baseline to compute ratios
    segment = db.query(Segment).filter(Segment.segment_id == request.road_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail=f"Segment {request.road_id} not found.")
        
    baseline = db.query(HistoricalMemory).filter(
        HistoricalMemory.segment_id == request.road_id,
        HistoricalMemory.hour_of_day == 12
    ).first()
    if not baseline:
        raise HTTPException(status_code=404, detail=f"Baseline memory for segment {request.road_id} at hour 12 not found.")

    # 2. Compute the 10 features (N_FEATURES = 10)
    # The signature extractor applies the following floors
    baseline_speed = max(baseline.avg_speed_kmph, 1.0)
    # Baseline density expects an expected count for a 20min window.
    # From signature_extractor.py: expected = baseline.avg_vehicle_count * (20.0 / 60.0)
    expected_density = max(baseline.avg_vehicle_count * (20.0 / 60.0), 0.5)
    
    speed_ratio = request.speed / baseline_speed
    density_ratio = request.density / expected_density
    
    # We don't have live uturn or variance from the frontend UI.
    # Following windowing.py fallback logic when len(speeds) <= 1 or uturn_count == 0
    uturn_ratio = 0.0
    variance_ratio = 0.0
    
    from datetime import datetime
    hour_of_day = datetime.utcnow().hour / 24.0
    
    road_type_idx = ROAD_TYPE_ORDINAL.get(segment.road_type, 0)
    lane_count = float(segment.number_of_lanes or 1.0)
    flood_prone = float(segment.flood_prone or 0.0)
    
    # We don't have live neighbor stats from a single segment prediction request.
    # Following windowing.py fallback logic when neighbors are missing
    neighbor_avg_speed = 0.0
    neighbor_density = 0.0

    # Build the exact 10-feature vector expected by the model
    feature_vector = np.array([
        speed_ratio,
        density_ratio,
        uturn_ratio,
        variance_ratio,
        hour_of_day,
        float(road_type_idx),
        lane_count,
        flood_prone,
        neighbor_avg_speed,
        neighbor_density
    ], dtype=np.float32)

    # 3. Load model and run inference
    model = get_model()
    
    with torch.no_grad():
        x_t = torch.tensor(feature_vector).unsqueeze(0)  # (1, 10)
        proba = model.net.predict_proba(x_t).squeeze(0)  # (8,)
    
    class_idx = int(torch.argmax(proba).item())
    confidence = float(proba[class_idx].item())
    prediction = IDX_TO_LABEL[class_idx]
    
    probabilities = {IDX_TO_LABEL[i]: float(proba[i].item()) for i in range(len(proba))}
    
    inference_time_ms = int((time.time() - start_time) * 1000)
    
    # OOD Detection
    is_ood = bool(speed_ratio > 3.0 or density_ratio > 7.0)
    warning_msg = None
    if is_ood:
        warning_msg = "Input is outside the training distribution. Prediction may be unreliable."
    else:
        warning_msg = "Prediction generated with partial feature availability (Missing: uturn, variance, neighbors)."

    # Feature completeness: 10 features total. 4 are missing live data (uturn, variance, neighbor_speed, neighbor_density)
    # 6 features are fully available (speed, density, hour, road_type, lane, flood)
    completeness = 60.0

    return PredictionResponse(
        prediction=prediction,
        confidence=confidence,
        probabilities=probabilities,
        inference_time_ms=inference_time_ms,
        feature_completeness=completeness,
        ood=is_ood,
        warning=warning_msg
    )
