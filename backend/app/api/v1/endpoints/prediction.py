"""Standalone Geo V2 inference endpoint; register in router.py when ready."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.geo_v2_repository import GeoV2Repository
from app.repositories.segment_repository import SegmentRepository
from app.schemas.geo_v2_inference import (
    GeoV2BatchInferenceRequest, GeoV2BatchInferenceResponse, GeoV2InferenceRequest,
    GeoV2InferenceResponse, TelemetryInferenceRequest, TelemetryInferenceResponse,
)
from app.services.geo_v2.prediction_service import GeoV2PredictionService
from app.services.geo_v2.runtime_inference import CausalFeatureContextCache, FEATURE_VERSION
from app.services.federated_learning.global_model import GLOBAL_MODEL_STORE
from app.services.geo_v2.inference import (
    HistoricalBaseline,
    NeighborAggregate,
    SegmentContext,
    TelemetryAggregate,
    infer_telemetry_state,
)

router = APIRouter(prefix="/prediction", tags=["prediction"])
_GEO_V2_CONTEXT_CACHE = CausalFeatureContextCache()


def _geo_v2_service(db: Session) -> GeoV2PredictionService:
    return GeoV2PredictionService(
        SegmentRepository(db), HistoricalMemoryRepository(db), GeoV2Repository(db), cache=_GEO_V2_CONTEXT_CACHE,
    )


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


@router.post("/infer/geo-v2", response_model=GeoV2InferenceResponse)
def infer_geo_v2_prediction(request: GeoV2InferenceRequest, db: Session = Depends(get_db)) -> GeoV2InferenceResponse:
    try:
        item, region, result = _geo_v2_service(db).infer_batch([request])[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _geo_v2_response(item, region, result)


@router.post("/infer/batch", response_model=GeoV2BatchInferenceResponse)
def infer_geo_v2_prediction_batch(
    request: GeoV2BatchInferenceRequest, db: Session = Depends(get_db),
) -> GeoV2BatchInferenceResponse:
    try:
        results = _geo_v2_service(db).infer_batch(request.items)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GeoV2BatchInferenceResponse(results=[_geo_v2_response(item, region, result) for item, region, result in results])


def _geo_v2_response(item, region: str, result) -> GeoV2InferenceResponse:
    return GeoV2InferenceResponse(
        status=result.status, segment_id=item.segment_id, region=region, timestamp=item.as_of,
        model_version=result.model_version, feature_version=FEATURE_VERSION, prediction=result.prediction,
        predicted_label=result.prediction, confidence=result.confidence, probabilities=result.probabilities,
        baseline=result.baseline, deviations=result.deviations,
    )
