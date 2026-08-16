from fastapi import APIRouter

from app.api.v1.endpoints import health, ingest, live_ingest, segments, routes, events, federated, metrics, predict

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ingest.router)
api_router.include_router(live_ingest.router)
api_router.include_router(segments.router)
api_router.include_router(routes.router)
api_router.include_router(events.router)
api_router.include_router(federated.router)
api_router.include_router(metrics.router)
api_router.include_router(predict.router)
