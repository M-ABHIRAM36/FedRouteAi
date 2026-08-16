"""Shared pytest fixtures.

`db_session`   : bare in-memory SQLite session — for unit tests that
                 only need the ORM, no API layer.
`client`        : a FastAPI TestClient wired to that SAME in-memory
                 session via dependency override — for integration
                 tests that go through actual HTTP endpoints. Using the
                 same engine/session across a test is what lets
                 "POST /ingest/gps then GET /events" work in one test.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.models import segment, region, gps_ping, event, historical_memory, fl_round_record, live_ingestion  # noqa: F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single shared in-memory DB across all connections in this test
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    from app.main import app
    from app.db.session import get_db
    from app.services.road_graph.graph_cache import GRAPH_CACHE

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    GRAPH_CACHE._graph = None  # each test starts with a cold cache

    # ingest.py's background task opens its own session directly via
    # SessionLocal — patch that name in both places it's imported so
    # background-task-triggered detection also lands in the test DB
    monkeypatch.setattr("app.db.session.SessionLocal", TestSession)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
