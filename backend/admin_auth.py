"""Admin authentication. The console does not exist (404) unless it is configured AND the caller holds a valid session."""
from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import Event, utcnow
from backend.deps import ClientMeta, get_hub
from backend.services.hub import ServiceHub
from forklens.exceptions import RateLimitExceededError

COOKIE = "s2c_admin"
AUDIENCE = "forklens-admin"
SESSION_HOURS = 8
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)


def issue_token(hub: ServiceHub) -> str:
    """Signed, short-lived admin session token."""
    now = datetime.now(timezone.utc)
    claims = {"sub": hub.settings.admin_username, "aud": AUDIENCE, "iat": now, "exp": now + timedelta(hours=SESSION_HOURS)}
    return jwt.encode(claims, hub.settings.admin_jwt_secret, algorithm="HS256")


def require_admin(request: Request, hub: ServiceHub = Depends(get_hub)) -> str:
    """Dependency for every admin route. Any failure answers 404 so the console cannot be discovered by probing."""
    settings = hub.settings
    if not settings.admin_enabled:
        raise HTTPException(404, "Not Found")
    header = request.headers.get("authorization", "")
    token = request.cookies.get(COOKIE) or (header[7:] if header.lower().startswith("bearer ") else "")
    try:
        claims = jwt.decode(token, settings.admin_jwt_secret, algorithms=["HS256"], audience=AUDIENCE)
    except jwt.PyJWTError as exc:
        raise HTTPException(404, "Not Found") from exc
    return str(claims["sub"])


def check_credentials(hub: ServiceHub, username: str, password: str) -> bool:
    """Constant-time comparison of both fields (no early exit that leaks which one was wrong)."""
    s = hub.settings
    user_ok = hmac.compare_digest(username.encode(), s.admin_username.encode())
    pass_ok = hmac.compare_digest(password.encode(), s.admin_password.encode())
    return user_ok and pass_ok


def enforce_lockout(session: Session, meta: ClientMeta) -> None:
    """Block an address after repeated failures (brute-force protection)."""
    since = utcnow() - LOCKOUT
    failures = session.scalar(select(func.count()).select_from(Event).where(
        Event.type == "admin_login_fail", Event.ip_hash == meta.ip_hash, Event.ts > since)) or 0
    if failures >= MAX_FAILURES:
        raise RateLimitExceededError("Too many failed admin logins", retry_after=int(LOCKOUT.total_seconds()))

