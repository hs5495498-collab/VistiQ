"""Shared pytest fixtures for the VISTIQ backend test suite.

Every test runs against an isolated in-memory SQLite database — never the
real vistiq-backend/data/vistiq.db — via FastAPI's get_db dependency
override. Nothing here touches real wardrobe data or uploaded files.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import connection
from app.database.connection import Base, get_db
from app.database.models import ClothingItem  # noqa: F401 (registers the model with Base.metadata)
from app.main import app
from app.services import image_storage


@pytest.fixture
def test_engine():
    """A fresh in-memory SQLite database, isolated per test. StaticPool keeps
    the same connection alive for the whole test instead of each new
    connection getting its own empty :memory: database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """A raw SQLAlchemy session for tests that call business logic
    (e.g. the recommendation engine) directly, without going through HTTP."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_engine, tmp_path, monkeypatch):
    """A FastAPI TestClient wired to the isolated test database via
    dependency override — every route under test hits `test_engine`, never
    the real database file. Uploaded test images are redirected to a
    pytest-managed tmp_path too, so tests never write into the real
    vistiq-backend/data/uploads/ directory.

    `TestClient` used as a context manager runs the app's real startup
    lifespan, which calls `init_db()` — and `init_db()` reads the module-
    global `connection.engine`, NOT the `get_db` dependency override. Without
    also patching that global, lifespan would silently run schema
    create/migrate logic against the real production `vistiq.db` on every
    single test. Patching it here keeps that fully inside `test_engine` too.
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(connection, "engine", test_engine)
    monkeypatch.setattr(image_storage, "UPLOADS_DIR", tmp_path)

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_item(db_session, **overrides) -> ClothingItem:
    """Test helper: insert a ClothingItem with sensible defaults, overridden
    by whatever the caller passes."""
    defaults = dict(
        name="Test Item",
        category="Tops",
        color="Black",
        style="Casual",
        occasion="Casual",
        season="All Season",
        wear_count=0,
    )
    defaults.update(overrides)
    item = ClothingItem(**defaults)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item
