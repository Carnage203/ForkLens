"""Engine and session handling, tuned for serverless (no long-lived pools) and for plain local dev."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from backend.db.models import Base

log = logging.getLogger("snap2cook.db")
ROOT = Path(__file__).resolve().parent.parent.parent


def normalise_url(url: str) -> str:
    """Accept the URLs providers hand out (postgres://, postgresql://) and pin the psycopg 3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Database:
    """Owns the SQLAlchemy engine. Empty URL means a local SQLite file; ``sqlite://`` is in-memory (tests)."""

    def __init__(self, url: str = "", serverless: bool = False) -> None:
        self._url = normalise_url(url) if url else f"sqlite:///{(ROOT / 'dev.db').as_posix()}"
        self._engine = self._build_engine(serverless)
        self._factory = sessionmaker(self._engine, expire_on_commit=False)

    def _build_engine(self, serverless: bool) -> Engine:
        if self._url.startswith("sqlite"):
            kwargs: dict = {"connect_args": {"check_same_thread": False}}
            if self._url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
            return create_engine(self._url, **kwargs)
        # Postgres behind Supabase's transaction pooler (pgbouncer): no server-side prepared statements.
        kwargs = {"connect_args": {"prepare_threshold": None, "connect_timeout": 10}, "pool_pre_ping": True}
        if serverless:
            kwargs["poolclass"] = NullPool  # each invocation is short-lived; the pooler does the pooling
        else:
            kwargs.update(pool_size=5, max_overflow=10, pool_recycle=300)
        return create_engine(self._url, **kwargs)

    @property
    def dialect(self) -> str:
        """'sqlite' or 'postgresql'."""
        return self._engine.dialect.name

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: rolls back on error, always closes."""
        session = self._factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_all(self) -> None:
        """Create missing tables (idempotent)."""
        Base.metadata.create_all(self._engine)

    def ping(self) -> bool:
        """True when the database answers a trivial query."""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            log.warning("database ping failed: %s", type(exc).__name__)
            return False
