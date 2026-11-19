"""Database-backed L2 cache: shared by every serverless instance, so a photo analysed once is free forever after."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models import CacheEntry
from backend.db.session import Database
from forklens.cache import Cache

log = logging.getLogger("forklens.dbcache")
DEFAULT_TTL_S = 7 * 24 * 3600


class DbCache(Cache):
    """Key/value cache in the ``cache_entries`` table. Any database problem is a miss, never an error."""

    def __init__(self, db: Database, clock: Callable[[], float] = time.time) -> None:
        self._db = db
        self._clock = clock

    @staticmethod
    def _key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        try:
            with self._db.session() as session:
                row = session.get(CacheEntry, self._key(key))
                return row.value if row is not None and row.expires_at > self._clock() else None
        except SQLAlchemyError as exc:
            log.warning("cache read failed: %s", type(exc).__name__)
            return None

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        try:
            with self._db.session() as session:
                session.merge(CacheEntry(key=self._key(key), value=value,
                                         expires_at=self._clock() + (ttl or DEFAULT_TTL_S)))
                session.commit()
        except (SQLAlchemyError, TypeError) as exc:
            log.warning("cache write skipped: %s", type(exc).__name__)

    def purge_expired(self) -> int:
        """Delete expired rows (called by the daily cron). Returns how many were removed."""
        with self._db.session() as session:
            result = session.execute(delete(CacheEntry).where(CacheEntry.expires_at < self._clock()))
            session.commit()
            return result.rowcount or 0
