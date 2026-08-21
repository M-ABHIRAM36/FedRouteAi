from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.geo_v2_repository import GeoV2Repository
from app.schemas.live_scenario import ScenarioCreateIn, ScenarioOut
from app.services.geo_v2.scenarios import build_scenario_rows


router = APIRouter(prefix="/live-scenarios", tags=["live-scenarios"])


@router.post("", response_model=list[ScenarioOut])
def create_scenarios(request: ScenarioCreateIn, db: Session = Depends(get_db)):
    repository = GeoV2Repository(db)
    segment_ids = {item.segment_id for item in request.scenarios}
    regions = repository.segment_regions(segment_ids)
    try:
        rows = build_scenario_rows(
            request.source_id, request.run_id, request.scenarios, regions,
            repository.transitions_for_segments(segment_ids), datetime.utcnow(),
            repository.scenario_count() + 1,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return repository.save_scenarios(rows)


@router.get("", response_model=list[ScenarioOut])
def list_active_scenarios(
    source_id: str = Query(max_length=60),
    run_id: str = Query(max_length=80),
    at: datetime | None = None,
    db: Session = Depends(get_db),
):
    return GeoV2Repository(db).active_scenarios(source_id, run_id, at or datetime.utcnow())
