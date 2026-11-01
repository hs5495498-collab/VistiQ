"""SQLAlchemy engine/session setup for the VISTIQ SQLite database."""

from pathlib import Path

from sqlalchemy import create_engine
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
    """Create all tables that don't already exist."""
    from app.database import models  # noqa: F401  (registers models with Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
