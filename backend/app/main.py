from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.core.logging_config import get_logger
from app.api.v1.router import api_router
from app.db.session import SessionLocal
from app.services.road_graph.graph_cache import GRAPH_CACHE
# Register every mapper before requests can trigger SQLAlchemy flush ordering.
from app.models import segment, region, gps_ping, event, historical_memory, fl_round_record, live_ingestion, geo_v2  # noqa: F401

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        GRAPH_CACHE.refresh(db)
    except Exception:
        logger.warning("Could not warm graph cache at startup (DB not ready?) — will build on first use.")
    finally:
        db.close()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
artifacts_root = os.path.join(BASE_DIR, "app", "ml", "artifacts")

if os.path.exists(artifacts_root):
    app.mount("/artifacts", StaticFiles(directory=artifacts_root), name="artifacts")

@app.get("/artifacts/{filename}")
def serve_root_artifact_fallback(filename: str):
    # Fallback for top-level artifact requests pointing to adaptive_federated
    fallback_path = os.path.join(artifacts_root, "adaptive_federated", filename)
    if os.path.exists(fallback_path):
        return FileResponse(fallback_path)
    return {"error": f"Artifact {filename} not found"}

@app.get("/")
def root():
    return {"service": settings.APP_NAME, "docs": "/docs"}