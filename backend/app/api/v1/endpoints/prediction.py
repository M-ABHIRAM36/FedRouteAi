"""Standalone Geo V2 inference endpoint; register in router.py when ready."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.geo_v2_repository import GeoV2Repository
from app.repositories.segment_repository import SegmentRepository
from app.schemas.geo_v2_inference import TelemetryInferenceRequest, TelemetryInferenceResponse
from app.services.federated_learning.global_model import GLOBAL_MODEL_STORE
from app.services.geo_v2.inference import (
    HistoricalBaseline,
    NeighborAggregate,
    SegmentContext,
    TelemetryAggregate,
    infer_telemetry_state,
)

router = APIRouter(prefix="/prediction", tags=["prediction"])


@router.post("/infer", response_model=TelemetryInferenceResponse)
def infer_prediction(
    request: TelemetryInferenceRequest,
    db: Session = Depends(get_db),
) -> TelemetryInferenceResponse:
    segment = SegmentRepository(db).get(request.segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail=f"Segment {request.segment_id} not found")

    baseline_row = HistoricalMemoryRepository(db).get_baseline(request.segment_id, request.as_of.hour)
    if baseline_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Baseline for segment {request.segment_id} at hour {request.as_of.hour} not found",
        )

    result = infer_telemetry_state(
        telemetry=TelemetryAggregate(**request.telemetry.model_dump()),
        baseline=HistoricalBaseline(
            avg_speed_kmph=baseline_row.avg_speed_kmph,
            std_speed_kmph=baseline_row.std_speed_kmph,
            avg_vehicle_count=baseline_row.avg_vehicle_count,
            uturn_rate=baseline_row.uturn_rate,
            sample_size=baseline_row.sample_size,
        ),
        segment=SegmentContext(
            hour_of_day=request.as_of.hour,
            road_type=segment.road_type,
            lane_count=segment.number_of_lanes,
            flood_prone=segment.flood_prone,
        ),
        neighbors=[NeighborAggregate(**item.model_dump()) for item in request.neighbors],
        predictor=GLOBAL_MODEL_STORE,
    )
    values = asdict(result)
    GeoV2Repository(db).save_prediction({
        "source_id": request.source_id,
        "run_id": request.run_id,
        "segment_id": request.segment_id,
        "timestamp": request.as_of,
        "predicted_label": result.prediction,
        "confidence": result.confidence,
        "class_probabilities": result.probabilities,
        "model_version": result.model_version,
        "historical_baseline": result.baseline,
        "current_deviation": result.deviations,
    })
    return TelemetryInferenceResponse(segment_id=request.segment_id, timestamp=request.as_of, **values)
