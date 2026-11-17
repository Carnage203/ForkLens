"""ServiceHub: lazily builds the long-lived collaborators once per process (i.e. once per cold start)."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from backend.db.session import Database
from backend.services.cache import DbCache
from backend.services.limiter import DbRateLimiter
from backend.services.supabase_auth import SupabaseVerifier
from snap2cook.bootstrap import App, build_app
from snap2cook.cache import LRUCache, TieredCache
from snap2cook.config import Settings
from snap2cook.logging_setup import setup_logging
from snap2cook.models import Recipe

log = logging.getLogger("snap2cook.hub")


@dataclass(frozen=True)
class Services:
    """Everything a request handler may need."""

    settings: Settings
    db: Database
    app: App
    recipes: dict[str, Recipe]
    cache: DbCache
    limiter: DbRateLimiter
    scan_limiter: DbRateLimiter
    verifier: SupabaseVerifier | None


def build_services(settings: Settings, db: Database | None = None) -> Services:
    """Wire the database, caches, limiters and the AI pipeline together (dependency injection)."""
    setup_logging(settings)
    db = db or Database(settings.database_url, serverless=settings.env == "prod")
    db.create_all()
    cache = DbCache(db)
    limiter = DbRateLimiter(db, "generation", settings.guest_gen_limit, settings.user_gen_limit,
                            settings.rate_limit_window_s, settings.daily_limit, settings.ip_limit_factor)
    scan_limiter = DbRateLimiter(db, "scan", settings.guest_scan_limit, settings.user_scan_limit,
                                 settings.rate_limit_window_s, settings.daily_limit * 2, settings.ip_limit_factor)
    app = build_app(settings, TieredCache(LRUCache(512), cache), limiter, scan_limiter)
    verifier = SupabaseVerifier(settings.supabase_url, settings.supabase_anon_key) if settings.auth_enabled else None
    log.info("services ready: db=%s mode=%s corpus=%s", db.dialect, app.pipeline.mode, app.corpus_source)
    return Services(settings, db, app, {r.id: r for r in app.corpus}, cache, limiter, scan_limiter, verifier)


class ServiceHub:
    """Thread-safe lazy holder (double-checked locking) so import time stays fast on serverless."""

    def __init__(self, settings: Settings, db: Database | None = None) -> None:
        self._settings, self._db = settings, db
        self._services: Services | None = None
        self._lock = threading.Lock()

    @property
    def settings(self) -> Settings:
        """The immutable settings (available without building anything)."""
        return self._settings

    @property
    def services(self) -> Services:
        """Build on first use."""
        if self._services is None:
            with self._lock:
                if self._services is None:
                    self._services = build_services(self._settings, self._db)
        return self._services
