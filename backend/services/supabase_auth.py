"""Verifies Supabase access tokens by asking Supabase itself (works with any signing-key setup)."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass

import requests

log = logging.getLogger("forklens.auth")


@dataclass(frozen=True)
class AuthUser:
    """A verified Supabase user."""

    id: str
    email: str | None
    name: str | None


class SupabaseVerifier:
    """GET ``/auth/v1/user`` with the bearer token; successful answers are cached for a minute."""

    def __init__(self, url: str, anon_key: str, ttl_s: int = 60, timeout_s: int = 5) -> None:
        self._url, self._key, self._ttl, self._timeout = url, anon_key, ttl_s, timeout_s
        self._cache: dict[str, tuple[float, AuthUser]] = {}
        self._lock = threading.Lock()

    def verify(self, token: str) -> AuthUser | None:
        """Return the user for a valid token, else None (never raises)."""
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(digest)
            if hit and hit[0] > now:
                return hit[1]
        try:
            response = requests.get(f"{self._url}/auth/v1/user", timeout=self._timeout,
                                    headers={"Authorization": f"Bearer {token}", "apikey": self._key})
        except requests.RequestException as exc:
            log.warning("Supabase auth unreachable: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            return None
        body = response.json()
        meta = body.get("user_metadata") or {}
        user = AuthUser(body["id"], body.get("email"), meta.get("full_name") or meta.get("name"))
        with self._lock:
            if len(self._cache) > 2000:
                self._cache.clear()
            self._cache[digest] = (now + self._ttl, user)
        return user
