from fastapi import APIRouter

from app.api.v1.endpoints import health, segments, ingest, events, routes, federated

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(segments.router)
api_router.include_router(ingest.router)
api_router.include_router(events.router)
api_router.include_router(routes.router)
api_router.include_router(federated.router)
