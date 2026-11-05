from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def _read_only_args(url: URL) -> tuple[URL, dict]:
    """URL and connect arguments that make every connection read-only."""
    if url.get_backend_name() == "postgresql":
        return url, {"options": "-c default_transaction_read_only=on"}
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            raise ValueError("a read-only SQLite database needs a file path")
        return url.set(database=f"file:{url.database}",
                       query={**url.query, "mode": "ro", "uri": "true"}), {}
    raise ValueError(f"read-only mode is not supported for {url.get_backend_name()}")


def make_engine(url: str, read_only: bool = False) -> Engine:
    connect_args: dict = {}
    if read_only:
        parsed, connect_args = _read_only_args(make_url(url))
        url = parsed.render_as_string(hide_password=False)
    engine = create_engine(url, future=True, connect_args=connect_args)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def init_db(engine: Engine) -> None:
    """Create tables if missing. (Alembic migrations are a TODO, see docs/issues.md.)"""
    Base.metadata.create_all(engine)


def make_session_factory(url: str, read_only: bool = False) -> sessionmaker[Session]:
    """Session factory; creates missing tables unless ``read_only`` (then the database
    must already hold them, and any write fails)."""
    engine = make_engine(url, read_only)
    if not read_only:
        init_db(engine)
    return sessionmaker(engine, expire_on_commit=False)
