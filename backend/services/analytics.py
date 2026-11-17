"""Aggregations behind the admin dashboard. Portable SQL (group by day columns) plus light Python for percentiles."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session

from backend.db.models import Event, Feedback, Owner, RecipeRun, RequestLog, day_of, utcnow

AI_PATHS = ("/api/scan", "/api/recipes/generate")


def percentile(values: list[int], pct: float) -> int:
    """Nearest-rank percentile (0 for an empty list)."""
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def _days(days: int) -> list[str]:
    today = utcnow()
    return [day_of(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]


def overview(session: Session, days: int) -> dict[str, Any]:
    """Everything the Overview tab shows, for the last ``days`` days."""
    labels = _days(days)
    since_day, now = labels[0], utcnow()
    app_requests = (RequestLog.day >= since_day, ~RequestLog.path.like("/api/admin%"))
    scalar = lambda stmt: session.scalar(stmt) or 0  # noqa: E731

    users = {
        "total": scalar(select(func.count()).select_from(Owner)),
        "registered": scalar(select(func.count()).select_from(Owner).where(Owner.kind == "user")),
        "new": scalar(select(func.count()).select_from(Owner).where(Owner.created_at >= now - timedelta(days=days))),
        "active_24h": scalar(select(func.count()).select_from(Owner).where(Owner.last_seen_at >= now - timedelta(days=1))),
        "active_7d": scalar(select(func.count()).select_from(Owner).where(Owner.last_seen_at >= now - timedelta(days=7))),
    }
    total = scalar(select(func.count()).select_from(RequestLog).where(*app_requests))
    errors = scalar(select(func.count()).select_from(RequestLog).where(*app_requests, RequestLog.status >= 500))
    limited = scalar(select(func.count()).select_from(RequestLog).where(*app_requests, RequestLog.status == 429))
    latency = {}
    for path in AI_PATHS:
        durations = list(session.scalars(select(RequestLog.duration_ms).where(
            RequestLog.path == path, RequestLog.status < 400, RequestLog.day >= since_day).order_by(RequestLog.id.desc()).limit(3000)))
        latency[path] = {"p50": percentile(durations, 50), "p95": percentile(durations, 95), "count": len(durations)}

    per_day = {r.day: {"requests": r.n, "errors": int(r.e or 0)} for r in session.execute(
        select(RequestLog.day, func.count().label("n"), func.sum(case((RequestLog.status >= 500, 1), else_=0)).label("e"))
        .where(*app_requests).group_by(RequestLog.day))}
    events: dict[str, dict[str, int]] = {}
    for day, kind, n in session.execute(select(Event.day, Event.type, func.count()).where(
            Event.day >= since_day, Event.type.in_(("scan", "recipe", "cooked", "save"))).group_by(Event.day, Event.type)):
        events.setdefault(day, {})[kind] = n
    new_users = {str(d): n for d, n in session.execute(select(func.date(Owner.created_at), func.count()).where(
        Owner.created_at >= now - timedelta(days=days)).group_by(func.date(Owner.created_at)))}
    series = [{"day": d, "requests": per_day.get(d, {}).get("requests", 0), "errors": per_day.get(d, {}).get("errors", 0),
               "scans": events.get(d, {}).get("scan", 0), "recipes": events.get(d, {}).get("recipe", 0),
               "cooked": events.get(d, {}).get("cooked", 0), "new_users": new_users.get(d, 0)} for d in labels]

    runs = (RecipeRun.day >= since_day,)
    run_total = scalar(select(func.count()).select_from(RecipeRun).where(*runs))
    group = lambda col: {k: n for k, n in session.execute(select(col, func.count()).where(*runs).group_by(col))}  # noqa: E731
    flags = session.execute(select(func.sum(cast(RecipeRun.fallback_used, Integer)), func.sum(cast(RecipeRun.cache_hit, Integer)),
                                   func.sum(case((RecipeRun.recipe.is_(None), 1), else_=0))).where(*runs)).one()
    ingredient_counter: Counter[str] = Counter()
    for ingredients in session.scalars(select(RecipeRun.ingredients).where(*runs).order_by(RecipeRun.ts.desc()).limit(1500)):
        ingredient_counter.update(ingredients or [])
    scan_models = Counter((d or {}).get("model") or "cache/none" for d in session.scalars(
        select(Event.data).where(Event.type == "scan", Event.day >= since_day).order_by(Event.id.desc()).limit(2000)))
    endpoints = [{"path": p, "count": n, "avg_ms": int(avg or 0), "errors": int(e or 0)} for p, n, avg, e in session.execute(
        select(RequestLog.path, func.count().label("n"), func.avg(RequestLog.duration_ms),
               func.sum(case((RequestLog.status >= 500, 1), else_=0))).where(*app_requests)
        .group_by(RequestLog.path).order_by(func.count().desc()).limit(12))]
    countries = [{"country": c or "unknown", "users": n} for c, n in session.execute(
        select(Owner.country, func.count()).group_by(Owner.country).order_by(func.count().desc()).limit(8))]
    rating = session.execute(select(func.avg(Feedback.rating), func.count()).where(Feedback.ts >= now - timedelta(days=days))).one()
    today = day_of()
    quota = {k: scalar(select(func.count()).select_from(Event).where(Event.type == f"quota:{k}", Event.day == today))
             for k in ("scan", "generation")}

    return {
        "days": days, "users": users,
        "requests": {"total": total, "errors": errors, "rate_limited": limited,
                     "error_rate": round(errors / total, 4) if total else 0.0},
        "latency": latency, "series": series, "quota_today": quota,
        "recipes": {"total": run_total, "tiers": group(RecipeRun.tier), "diets": group(RecipeRun.diet),
                    "fallback": int(flags[0] or 0), "cache_hits": int(flags[1] or 0), "no_recipe": int(flags[2] or 0),
                    "gen_models": {(k or "verbatim/cache"): n for k, n in group(RecipeRun.gen_model).items()}},
        "vision_models": dict(scan_models.most_common(8)),
        "top_ingredients": [{"name": n, "count": c} for n, c in ingredient_counter.most_common(12)],
        "endpoints": endpoints, "countries": countries,
        "feedback": {"avg": round(float(rating[0] or 0), 2), "count": int(rating[1] or 0)},
    }
