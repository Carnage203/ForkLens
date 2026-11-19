"""FastAPI dependencies: services, DB session, caller identity and request metadata."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.models import Owner, utcnow
from backend.services.hub import ServiceHub, Services

CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
TOUCH_EVERY = timedelta(minutes=5)


@dataclass(frozen=True)
class Identity:
    """Who is calling: a signed-in user, or an anonymous guest identified by a browser-generated id."""

    owner_id: str
    is_user: bool
    email: str | None = None
    name: str | None = None
    guest_id: str | None = None  # the browser's guest owner id, kept so guest data can be claimed on login


@dataclass(frozen=True)
class ClientMeta:
    """Privacy-friendly request fingerprint (the raw IP is never stored)."""

    ip_hash: str
    country: str | None
    user_agent: str


def get_hub(request: Request) -> ServiceHub:
    """The process-wide hub created in ``create_app``."""
    return request.app.state.hub


def get_services(hub: ServiceHub = Depends(get_hub)) -> Services:
    """Built lazily on the first request."""
    return hub.services


def get_session(svc: Services = Depends(get_services)) -> Iterator[Session]:
    """A database session closed after the request."""
    with svc.db.session() as session:
        yield session


def get_meta(request: Request, hub: ServiceHub = Depends(get_hub)) -> ClientMeta:
    """Hash the caller's IP with a server-side salt; keep country (Vercel header) and a trimmed user agent."""
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    salt = hub.settings.admin_jwt_secret or "forklens"
    return ClientMeta(hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:16],
                      request.headers.get("x-vercel-ip-country"), request.headers.get("user-agent", "")[:200])


def get_identity(request: Request, session: Session = Depends(get_session), svc: Services = Depends(get_services),
                 meta: ClientMeta = Depends(get_meta), authorization: str | None = Header(None),
                 x_client_id: str | None = Header(None)) -> Identity:
    """Resolve the caller: valid Supabase bearer token -> user, otherwise the guest client id header."""
    guest = f"g_{x_client_id}" if x_client_id and CLIENT_ID.match(x_client_id) else None
    identity: Identity | None = None
    if authorization and authorization.lower().startswith("bearer ") and svc.verifier is not None:
        user = svc.verifier.verify(authorization[7:].strip())
        if user is not None:
            identity = Identity(user.id, True, user.email, user.name, guest)
    if identity is None:
        if guest is None:
            raise HTTPException(status_code=400, detail="Missing or invalid X-Client-Id header")
        identity = Identity(guest, False, guest_id=guest)
    _touch_owner(session, identity, meta)
    request.state.owner_id = identity.owner_id
    return identity


def _touch_owner(session: Session, identity: Identity, meta: ClientMeta) -> None:
    """Create the owner row on first sight; refresh last-seen at most every few minutes (cheap on the DB)."""
    now = utcnow()
    owner = session.get(Owner, identity.owner_id)
    if owner is None:
        session.add(Owner(id=identity.owner_id, kind="user" if identity.is_user else "guest", email=identity.email,
                          display_name=identity.name, country=meta.country, created_at=now, last_seen_at=now))
        try:
            session.commit()
        except IntegrityError:  # another request created it first
            session.rollback()
    elif now - owner.last_seen_at > TOUCH_EVERY or (identity.email and owner.email != identity.email):
        owner.last_seen_at, owner.email = now, identity.email or owner.email
        owner.display_name = identity.name or owner.display_name
        owner.country = meta.country or owner.country
        session.commit()
