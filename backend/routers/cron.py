"""Scheduled maintenance, invoked by Vercel Cron (which sends ``Authorization: Bearer $CRON_SECRET``)."""
from __future__ import annotations

import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.db.models import Event, RequestLog, utcnow
from backend.deps import get_services, get_session
from backend.services.hub import Services

router = APIRouter(prefix="/api/cron")


@router.get("/cleanup")
def cleanup(request: Request, svc: Services = Depends(get_services), session: Session = Depends(get_session)) -> dict:
    """Trim old rows so the free-tier database never fills up."""
    expected = svc.settings.cron_secret
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(404, "Not Found")
    now = utcnow()
    logs = session.execute(delete(RequestLog).where(RequestLog.ts < now - timedelta(days=30))).rowcount or 0
    events = session.execute(delete(Event).where(Event.ts < now - timedelta(days=90))).rowcount or 0
    session.commit()
    return {"request_logs": logs, "events": events, "cache": svc.cache.purge_expired()}
