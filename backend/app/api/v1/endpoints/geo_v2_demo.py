from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies.geo_v2_demo import get_geo_v2_demo_service
from app.schemas.geo_v2_demo import GeoV2DemoCreateIn, GeoV2DemoRunOut, GeoV2DemoStepOut
from app.services.geo_v2.demo_runtime import GeoV2DemoService


router = APIRouter(prefix="/demo/geo-v2", tags=["geo-v2-demo"])


@router.post("/runs", response_model=GeoV2DemoRunOut, status_code=status.HTTP_201_CREATED)
def create_demo_run(request: GeoV2DemoCreateIn, service: GeoV2DemoService = Depends(get_geo_v2_demo_service)):
    try:
        return service.create(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/runs/{run_id}", response_model=GeoV2DemoRunOut)
def get_demo_run(run_id: str, service: GeoV2DemoService = Depends(get_geo_v2_demo_service)):
    try:
        return service.status(run_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/runs/{run_id}/step", response_model=GeoV2DemoStepOut)
def step_demo(run_id: str, service: GeoV2DemoService = Depends(get_geo_v2_demo_service)):
    try:
        return service.step(run_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def stop_demo_run(run_id: str, service: GeoV2DemoService = Depends(get_geo_v2_demo_service)):
    service.stop(run_id)
