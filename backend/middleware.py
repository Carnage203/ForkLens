"""Pure-ASGI middleware: request id, timing, security headers and the request log written to the database."""
from __future__ import annotations

import logging
import time
from hashlib import sha256

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.db.models import Owner, RequestLog
from backend.services.hub import ServiceHub
from forklens.logging_setup import new_request_id

log = logging.getLogger("forklens.requests")
SKIP = {"/api/health"}
SECURITY_HEADERS = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(self), microphone=(), geolocation=()")]


class RequestLogMiddleware:
    """Wraps every HTTP request. Logging happens after the response bytes are sent, so it adds no latency."""

    def __init__(self, app: ASGIApp, hub: ServiceHub) -> None:
        self.app, self._hub = app, hub

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        request_id = new_request_id()
        scope.setdefault("state", {})["request_id"] = request_id
        status = 500
        crashed: str | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode()), *SECURITY_HEADERS]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:  # re-raised: FastAPI's handler builds the 500 response
            crashed = f"{type(exc).__name__}: {exc}"[:500]
            raise
        finally:
            path = scope["path"]
            if path.startswith("/api") and path not in SKIP and scope["method"] != "OPTIONS":
                state = scope["state"]
                await run_in_threadpool(self._write, scope, status, int((time.perf_counter() - started) * 1000),
                                        request_id, state.get("owner_id"), crashed or state.get("error"))

    def _write(self, scope: Scope, status: int, ms: int, request_id: str, owner_id: str | None, error: str | None) -> None:
        headers = {k.decode(): v.decode() for k, v in scope["headers"]}
        ip = headers.get("x-forwarded-for", "").split(",")[0].strip() or (scope["client"][0] if scope.get("client") else "")
        salt = self._hub.settings.admin_jwt_secret or "forklens"
        try:
            with self._hub.services.db.session() as session:
                session.add(RequestLog(request_id=request_id, method=scope["method"], path=scope["path"][:200], status=status,
                                       duration_ms=ms, owner_id=owner_id, ip_hash=sha256(f"{salt}:{ip}".encode()).hexdigest()[:16],
                                       user_agent=headers.get("user-agent", "")[:200], error=error))
                if owner_id:
                    session.execute(update(Owner).where(Owner.id == owner_id).values(request_count=Owner.request_count + 1))
                session.commit()
        except SQLAlchemyError as exc:
            log.warning("request log write failed: %s", type(exc).__name__)
