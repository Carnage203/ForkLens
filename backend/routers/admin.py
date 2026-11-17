"""Admin console API. Every route except login requires a valid admin session and otherwise answers 404."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend import admin_auth
from backend.admin_auth import require_admin
from backend.db.models import (CacheEntry, Event, Feedback, Owner, RecipeRun, RequestLog, SavedRecipe, day_of, utcnow)
from backend.errors import AdminAuthError
from backend.deps import ClientMeta, get_hub, get_meta, get_services, get_session
from backend.schemas import AdminLoginIn
from backend.services import analytics
from backend.services.helpers import record_event
from backend.services.hub import ServiceHub, Services

router = APIRouter(prefix="/api/admin")
protected = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/login")
def login(body: AdminLoginIn, response: Response, hub: ServiceHub = Depends(get_hub), meta: ClientMeta = Depends(get_meta),
          session: Session = Depends(get_session)) -> dict:
    """Exchange the admin credentials for an httpOnly session cookie (5 failures -> 15 min lockout)."""
    if not hub.settings.admin_enabled:
        raise HTTPException(404, "Not Found")
    admin_auth.enforce_lockout(session, meta)
    if not admin_auth.check_credentials(hub, body.username, body.password):
        record_event(session, None, meta.ip_hash, "admin_login_fail")
        session.commit()
        raise AdminAuthError("bad admin credentials")
    record_event(session, None, meta.ip_hash, "admin_login")
    session.commit()
    response.set_cookie(admin_auth.COOKIE, admin_auth.issue_token(hub), httponly=True, samesite="strict",
                        secure=hub.settings.env == "prod", max_age=admin_auth.SESSION_HOURS * 3600, path="/api/admin")
    return {"ok": True, "username": hub.settings.admin_username}


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(admin_auth.COOKIE, path="/api/admin")
    return {"ok": True}


@protected.get("/session")
def whoami(user: str = Depends(require_admin)) -> dict:
    """Used by the SPA to decide between the login form and the dashboard."""
    return {"ok": True, "username": user}


@protected.get("/overview")
def overview(days: int = Query(14, ge=1, le=90), session: Session = Depends(get_session)) -> dict:
    """KPIs, time series and breakdowns."""
    return analytics.overview(session, days)


@protected.get("/requests")
def requests_log(limit: int = Query(50, le=200), offset: int = 0, min_status: int = 0, path: str = "", owner: str = "",
                 session: Session = Depends(get_session)) -> dict:
    """Paginated request log with filters."""
    where = [RequestLog.status >= min_status, ~RequestLog.path.like("/api/admin%")]
    if path:
        where.append(RequestLog.path.like(f"%{path[:60]}%"))
    if owner:
        where.append(RequestLog.owner_id == owner)
    rows = session.scalars(select(RequestLog).where(*where).order_by(RequestLog.id.desc()).limit(limit).offset(offset))
    total = session.scalar(select(func.count()).select_from(RequestLog).where(*where)) or 0
    return {"total": total, "rows": [{"id": r.id, "ts": r.ts.isoformat() + "Z", "request_id": r.request_id, "method": r.method,
                                      "path": r.path, "status": r.status, "ms": r.duration_ms, "owner": r.owner_id,
                                      "ip": r.ip_hash, "error": r.error} for r in rows]}


@protected.get("/users")
def users(limit: int = Query(50, le=200), offset: int = 0, kind: str = "", session: Session = Depends(get_session)) -> dict:
    """Most recently active users and guests with their usage counts."""
    where = [Owner.kind == kind] if kind in ("user", "guest") else []
    page = list(session.scalars(select(Owner).where(*where).order_by(Owner.last_seen_at.desc()).limit(limit).offset(offset)))
    ids = [o.id for o in page]
    runs = dict(session.execute(select(RecipeRun.owner_id, func.count()).where(RecipeRun.owner_id.in_(ids)).group_by(RecipeRun.owner_id)).all())
    saved = dict(session.execute(select(SavedRecipe.owner_id, func.count()).where(SavedRecipe.owner_id.in_(ids)).group_by(SavedRecipe.owner_id)).all())
    total = session.scalar(select(func.count()).select_from(Owner).where(*where)) or 0
    return {"total": total, "rows": [{"id": o.id, "kind": o.kind, "email": o.email, "name": o.display_name, "country": o.country,
                                      "created": o.created_at.isoformat() + "Z", "last_seen": o.last_seen_at.isoformat() + "Z",
                                      "requests": o.request_count, "recipes": runs.get(o.id, 0), "saved": saved.get(o.id, 0)}
                                     for o in page]}


@protected.get("/runs")
def runs(limit: int = Query(50, le=200), offset: int = 0, session: Session = Depends(get_session)) -> dict:
    """Recent recipe requests: what people cook, how fast, and which model answered."""
    rows = session.scalars(select(RecipeRun).order_by(RecipeRun.ts.desc()).limit(limit).offset(offset))
    total = session.scalar(select(func.count()).select_from(RecipeRun)) or 0
    return {"total": total, "rows": [{"id": r.id, "ts": r.ts.isoformat() + "Z", "tier": r.tier, "diet": r.diet,
                                      "ingredients": r.ingredients, "title": (r.recipe or {}).get("title"), "ms": r.latency_ms,
                                      "model": r.gen_model, "fallback": r.fallback_used, "cache": r.cache_hit, "owner": r.owner_id}
                                     for r in rows]}


@protected.get("/feedback")
def feedback(limit: int = Query(50, le=200), session: Session = Depends(get_session)) -> dict:
    """Latest ratings and comments."""
    rows = session.scalars(select(Feedback).order_by(Feedback.id.desc()).limit(limit))
    return {"rows": [{"id": r.id, "ts": r.ts.isoformat() + "Z", "rating": r.rating, "category": r.category,
                      "comment": r.comment, "owner": r.owner_id, "run_id": r.run_id} for r in rows]}


@protected.get("/system")
def system(svc: Services = Depends(get_services), session: Session = Depends(get_session)) -> dict:
    """Configuration health: which integrations are configured (booleans only, never the secrets)."""
    s = svc.settings
    counts = {name: session.scalar(select(func.count()).select_from(model)) or 0
              for name, model in (("owners", Owner), ("request_logs", RequestLog), ("events", Event),
                                  ("recipe_runs", RecipeRun), ("cache_entries", CacheEntry), ("saved_recipes", SavedRecipe))}
    return {"env": s.env, "database": svc.db.dialect, "mode": svc.app.pipeline.mode, "corpus": svc.app.corpus_source,
            "recipes": len(svc.app.corpus),
            "keys": {"gemini": bool(s.gemini_api_key), "groq": bool(s.groq_api_key), "openrouter": bool(s.openrouter_api_key),
                     "supabase_auth": s.auth_enabled, "cron_secret": bool(s.cron_secret)},
            "models": {"vision": list(s.groq_vision_models) + [s.vision_model], "generation": list(s.groq_gen_models)},
            "rows": counts, "today": day_of(), "now": utcnow().isoformat() + "Z"}


@protected.post("/purge")
def purge(days: int = Query(30, ge=7, le=365), svc: Services = Depends(get_services), session: Session = Depends(get_session)) -> dict:
    """Delete request logs older than ``days`` and expired cache rows."""
    cutoff = utcnow() - timedelta(days=days)
    logs = session.execute(delete(RequestLog).where(RequestLog.ts < cutoff)).rowcount or 0
    session.commit()
    return {"request_logs_deleted": logs, "cache_deleted": svc.cache.purge_expired()}


router.include_router(protected)
