"""Distributed rate limiter. State lives in the ``events`` table, so limits hold across all serverless instances."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models import Event, day_of, utcnow
from backend.db.session import Database
from snap2cook.exceptions import RateLimitExceededError
from snap2cook.limiter import RateLimiter

log = logging.getLogger("snap2cook.dblimiter")


class DbRateLimiter(RateLimiter):
    """Sliding window per owner and per network address, plus a global daily ceiling.

    ``check`` receives ``"<owner_id>|<ip_hash>"``. Guests get a smaller allowance than signed-in users.
    The count-then-insert is not atomic, so a burst can overshoot by a request or two: acceptable for a
    quota guard (documented trade-off). If the database is down the limiter fails open and logs.
    """

    def __init__(self, db: Database, kind: str, guest_limit: int, user_limit: int, window_s: int,
                 daily_max: int, ip_factor: int = 3) -> None:
        super().__init__(guest_limit, window_s, daily_max)
        self._db, self._kind = db, f"quota:{kind}"
        self._guest, self._user, self._window, self._daily, self._ip_factor = guest_limit, user_limit, window_s, daily_max, ip_factor

    def check(self, session_id: str) -> None:
        """Record one use or raise RateLimitExceededError."""
        owner, _, ip = session_id.partition("|")
        limit = self._guest if owner.startswith("g_") or not owner else self._user
        since = utcnow() - timedelta(seconds=self._window)
        try:
            with self._db.session() as session:
                self._enforce(session, owner, ip, limit, since)
                session.add(Event(type=self._kind, owner_id=owner or None, ip_hash=ip or None, data={}))
                session.commit()
        except SQLAlchemyError as exc:
            log.warning("rate limiter unavailable, failing open: %s", type(exc).__name__)

    def _enforce(self, session, owner: str, ip: str, limit: int, since: datetime) -> None:
        count = lambda *where: session.scalar(select(func.count()).select_from(Event).where(Event.type == self._kind, *where)) or 0  # noqa: E731
        if count(Event.day == day_of()) >= self._daily:
            raise RateLimitExceededError("Global daily limit reached", retry_after=3600)
        if owner and count(Event.owner_id == owner, Event.ts > since) >= limit:
            oldest = session.scalar(select(func.min(Event.ts)).where(Event.type == self._kind, Event.owner_id == owner, Event.ts > since))
            raise RateLimitExceededError(f"Owner limit of {limit} per {self._window}s reached",
                                         retry_after=self._retry(oldest))
        if ip and count(Event.ip_hash == ip, Event.ts > since) >= limit * self._ip_factor:
            raise RateLimitExceededError("Network limit reached", retry_after=self._window // 2)

    def _retry(self, oldest: datetime | None) -> int:
        if oldest is None:
            return self._window
        return max(1, int((oldest + timedelta(seconds=self._window) - utcnow()).total_seconds()) + 1)
