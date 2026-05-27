"""SQLAlchemy 2.0 base — engine, session, and lifecycle helpers.

The engine is built lazily from ``settings.database_url``. SQLite gets WAL
mode and a sensible busy timeout; other backends use their defaults. Session
usage:

    from cve_monitor.db import db_session

    with db_session() as session:
        session.add(item)
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from cve_monitor.logging import get_logger
from cve_monitor.settings import get_settings

log = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    eng = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

    return eng


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency — yields a session and closes it on exit."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager: auto commit on success, rollback on failure."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables (idempotent)."""
    # Import models to register them on Base.metadata before create_all.
    from cve_monitor.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    log.info("database initialised", url=get_settings().database_url)


def reset_db() -> None:
    """Drop and recreate all tables. Destructive — for dev/testing only."""
    from cve_monitor.db import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    log.warning("database reset", url=get_settings().database_url)
