from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def make_engine(url: str) -> Engine:
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def init_db(engine: Engine) -> None:
    """Create tables if missing. (Alembic migrations are a TODO, see docs/issues.md.)"""
    Base.metadata.create_all(engine)


def make_session_factory(url: str) -> sessionmaker[Session]:
    engine = make_engine(url)
    init_db(engine)
    return sessionmaker(engine, expire_on_commit=False)
