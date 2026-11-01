"""SQLAlchemy engine/session setup for the VISTIQ SQLite database."""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# vistiq-backend/ — computed from this file's location so the database path
# is correct no matter which directory uvicorn is launched from.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'vistiq.db'}"

# check_same_thread=False is required because FastAPI can handle a single
# request's work across multiple threads.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class every ORM model inherits from."""


def init_db() -> None:
    """Create all tables that don't already exist, then apply any small
    additive column migrations by hand (no Alembic in this project's scope).

    `create_all()` only creates missing *tables* — it never alters an
    existing table's columns, so a database file created before a new
    column was added (e.g. a real local vistiq.db from before Phase 1's
    `is_favorite` column) would otherwise be left on the old schema and
    error out the first time that column is read/written. SQLite supports
    a plain `ALTER TABLE ... ADD COLUMN`, so this performs that one-time,
    idempotent fix-up automatically.
    """
    from app.database import models  # noqa: F401  (registers models with Base.metadata)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    if "clothing_items" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("clothing_items")}
    if "is_favorite" not in existing_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE clothing_items ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0")
            )
    if "color_reliability" not in existing_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE clothing_items ADD COLUMN color_reliability VARCHAR")
            )
    if "user_id" not in existing_columns:
        # Phase 4: nullable, no default — every pre-existing row ends up
        # with user_id=NULL (never deleted, never reassigned to a real
        # account automatically). See app/database/models.py's
        # ClothingItem.user_id docstring for why this is the deliberate,
        # approved choice rather than a one-time migration account.
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE clothing_items ADD COLUMN user_id INTEGER"))


def get_db() -> Session:
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
