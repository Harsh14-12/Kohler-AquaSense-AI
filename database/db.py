"""SQLAlchemy database helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base


def build_sqlite_url(database_path: Path) -> str:
    """Build a SQLite connection string from a local path."""

    return f"sqlite:///{database_path.as_posix()}"


def create_session_factory(database_path: Path) -> sessionmaker:
    """Create a SQLAlchemy session factory for the target database."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(build_sqlite_url(database_path), future=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(database_path: Path) -> None:
    """Create all tables if they do not already exist."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(build_sqlite_url(database_path), future=True)
    Base.metadata.create_all(engine)
