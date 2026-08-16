"""Run once (or via `scripts/seed_db.py`) to create tables + enable
PostGIS. Alembic should own schema changes after the first migration —
this is only for fast local bring-up."""
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.core.logging_config import get_logger

# import every model so Base.metadata knows about all tables
from app.models import segment, region, gps_ping, event, historical_memory, fl_round_record, live_ingestion  # noqa: F401

logger = get_logger(__name__)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized (tables created, PostGIS enabled).")


if __name__ == "__main__":
    init_db()
