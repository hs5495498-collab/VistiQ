"""Shared pytest fixtures for the VISTIQ backend test suite.

Every test runs against an isolated in-memory SQLite database — never the
real vistiq-backend/data/vistiq.db — via FastAPI's get_db dependency
override. Nothing here touches real wardrobe data or uploaded files.

Phase 4: every `db_session` automatically gets one default test user (see
`db_session` below) so the ~60 pre-Phase-4 `make_item(db_session, ...)`
call sites across the test suite didn't all need to be rewritten to pass
an explicit owner — `make_item` attaches new items to that default user
unless a test explicitly overrides `user_id` (e.g. to build a genuine
cross-user authorization test).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import connection
from app.database.connection import Base, get_db
from app.database.models import ClothingItem, User  # noqa: F401 (registers the models with Base.metadata)
from app.main import app
from app.security.passwords import hash_password
from app.services import image_storage, tryon_storage

TEST_USER_EMAIL = "test-user@example.com"
TEST_USER_PASSWORD = "correct-horse-battery"
TEST_USER_NAME = "Test User"

OTHER_USER_EMAIL = "other-user@example.com"
OTHER_USER_PASSWORD = "another-horse-battery"
OTHER_USER_NAME = "Other User"


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
    (e.g. the recommendation engine) directly, without going through HTTP.
    Seeds one default test user (see module docstring) so make_item()
    always has an owner to attach new items to."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    session.add(User(name=TEST_USER_NAME, email=TEST_USER_EMAIL, password_hash=hash_password(TEST_USER_PASSWORD)))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user_id(db_session) -> int:
    """The default test user's id — for tests calling build_recommendations()
    (or anything else that takes an explicit user_id) directly."""
    return db_session.query(User).filter(User.email == TEST_USER_EMAIL).one().id


@pytest.fixture
def client(test_engine, tmp_path, monkeypatch):
    """A FastAPI TestClient wired to the isolated test database via
    dependency override — every route under test hits `test_engine`, never
    the real database file. Uploaded test images are redirected to a
    pytest-managed tmp_path too, so tests never write into the real
    vistiq-backend/data/uploads/ directory.

    No user is registered/logged in on this client — use it directly for
    unauthenticated-access and registration/login tests; use
    `authenticated_client` below for everything that needs a logged-in
    session.

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
    monkeypatch.setattr(tryon_storage, "PERSON_IMAGES_DIR", tmp_path / "tryon_person_images")
    monkeypatch.setattr(tryon_storage, "RESULT_IMAGES_DIR", tmp_path / "tryon_results")
    (tmp_path / "tryon_person_images").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tryon_results").mkdir(parents=True, exist_ok=True)

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login(test_client: TestClient, email: str, password: str, name: str) -> None:
    """Registers (if needed) and logs in, then configures the client to
    automatically send the matching X-CSRF-Token header on every future
    request — TestClient's cookie jar already resends cookies
    automatically, but the double-submit CSRF header has to be set
    explicitly, exactly as the real frontend's api.ts does."""
    register_response = test_client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, "password_confirmation": password},
    )
    if register_response.status_code == 409:  # already registered by an earlier call on this client
        test_client.post("/auth/login", json={"email": email, "password": password})
    csrf_token = test_client.cookies.get("vistiq_csrf")
    assert csrf_token, "login/register did not set the CSRF cookie"
    test_client.headers["X-CSRF-Token"] = csrf_token


@pytest.fixture
def authenticated_client(client):
    """`client`, already logged in as a default test user, with the CSRF
    header pre-configured for every state-changing request."""
    _login(client, TEST_USER_EMAIL, TEST_USER_PASSWORD, TEST_USER_NAME)
    return client


@pytest.fixture
def second_authenticated_client(test_engine, tmp_path, monkeypatch):
    """A SEPARATE TestClient (own cookie jar) logged in as a second,
    different user — for cross-user authorization tests (User A's data
    must not be reachable by User B). Shares the same database as
    `client`/`authenticated_client` via `test_engine`, since a cross-user
    test needs both users to exist in the same database."""
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
    monkeypatch.setattr(tryon_storage, "PERSON_IMAGES_DIR", tmp_path / "tryon_person_images")
    monkeypatch.setattr(tryon_storage, "RESULT_IMAGES_DIR", tmp_path / "tryon_results")
    (tmp_path / "tryon_person_images").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tryon_results").mkdir(parents=True, exist_ok=True)

    with TestClient(app) as test_client:
        _login(test_client, OTHER_USER_EMAIL, OTHER_USER_PASSWORD, OTHER_USER_NAME)
        yield test_client


def make_item(db_session, **overrides) -> ClothingItem:
    """Test helper: insert a ClothingItem with sensible defaults, owned by
    the default test user (see module docstring) unless the caller passes
    an explicit user_id."""
    defaults = dict(
        name="Test Item",
        category="Tops",
        color="Black",
        style="Casual",
        occasion="Casual",
        season="All Season",
        wear_count=0,
    )
    if "user_id" not in overrides:
        defaults["user_id"] = db_session.query(User).filter(User.email == TEST_USER_EMAIL).one().id
    defaults.update(overrides)
    item = ClothingItem(**defaults)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item
