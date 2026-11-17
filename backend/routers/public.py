"""Public endpoints: health, app config, photo scan and recipe generation."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from backend.deps import ClientMeta, Identity, get_identity, get_meta, get_services, get_session
from backend.schemas import GenerateIn
from backend.services.helpers import new_id, recipe_payload, record_event
from backend.services.hub import Services
from backend.db.models import RecipeRun
from snap2cook.exceptions import InvalidImageError
from snap2cook.gemini import served_models
from snap2cook.models import Conditions
from snap2cook.tiers import TierFactory
from snap2cook.vision.image_utils import ImageValidator

router = APIRouter(prefix="/api")
VERSION = "2.0.0"
MAX_UPLOAD = 4_400_000  # Vercel rejects request bodies above 4.5 MB; the client compresses well below this


@router.get("/health")
def health(svc: Services = Depends(get_services)) -> dict:
    """Liveness + dependency status (used by uptime monitors)."""
    return {"status": "ok", "version": VERSION, "db": svc.db.ping(), "mode": svc.app.pipeline.mode,
            "recipes": len(svc.app.corpus)}


@router.get("/config")
def config(svc: Services = Depends(get_services)) -> dict:
    """Everything the client needs to render itself: options, limits and (public) auth settings."""
    s = svc.settings
    return {
        "version": VERSION, "mode": svc.app.pipeline.mode, "max_photos": s.max_photos,
        "extras": list(svc.app.pantry.extras), "vocabulary": svc.app.vocabulary,
        "diets": ["any", "veg", "vegan", "egg", "non-veg"], "time_options": [10, 15, 20, 30, 45, 60, 90],
        "limits": {"guest_per_window": s.guest_gen_limit, "user_per_window": s.user_gen_limit,
                   "window_minutes": s.rate_limit_window_s // 60},
        "auth": {"enabled": s.auth_enabled, "url": s.supabase_url, "anon_key": s.supabase_anon_key},
    }


def _session_key(identity: Identity, meta: ClientMeta) -> str:
    return f"{identity.owner_id}|{meta.ip_hash}"


@router.post("/scan")
def scan(files: list[UploadFile] = File(...), svc: Services = Depends(get_services), identity: Identity = Depends(get_identity),
         meta: ClientMeta = Depends(get_meta), session: Session = Depends(get_session)) -> dict:
    """Detect ingredients in up to N photos (Groq -> Gemini -> OpenRouter chain, cached by image hash)."""
    started, scratch = time.perf_counter(), {}
    served_models.set(scratch)
    if not files or len(files) > svc.settings.max_photos:
        raise InvalidImageError(f"{len(files)} photos sent", f"Please send between 1 and {svc.settings.max_photos} photos.")
    raws = [f.file.read(MAX_UPLOAD + 1) for f in files]
    if sum(len(r) for r in raws) > MAX_UPLOAD:
        raise InvalidImageError("Upload too large", "Those photos are too large. Try smaller photos.")
    validator = ImageValidator()
    images = [validator.prepare(raw) for raw in raws]
    series, empty = svc.app.pipeline.detect_many(images, _session_key(identity, meta))
    ingredients = [{"name": n, "confidence": round(float(c), 2)} for n, c in series.sort_values(ascending=False).items()]
    ms = int((time.perf_counter() - started) * 1000)
    record_event(session, identity.owner_id, meta.ip_hash, "scan", photos=len(images), found=len(ingredients), ms=ms,
                 model=scratch.get("vision"))
    session.commit()
    return {"ingredients": ingredients, "empty_photos": empty, "model": scratch.get("vision"), "latency_ms": ms}


@router.post("/recipes/generate")
def generate(body: GenerateIn, svc: Services = Depends(get_services), identity: Identity = Depends(get_identity),
             meta: ClientMeta = Depends(get_meta), session: Session = Depends(get_session)) -> dict:
    """Retrieve + rerank + generate a grounded recipe for the kitchen tier, then log the run."""
    started, scratch = time.perf_counter(), {}
    served_models.set(scratch)
    tier = TierFactory.create(body.tier, svc.app.pantry, body.equipment)
    result = svc.app.pipeline.recommend(body.ingredients, tier, Conditions(body.diet, body.max_time), body.extras,
                                        _session_key(identity, meta))
    ms = int((time.perf_counter() - started) * 1000)
    recipe = recipe_payload(result.recipe, svc.recipes) if result.recipe else None
    run_id = new_id()
    session.add(RecipeRun(id=run_id, owner_id=identity.owner_id, tier=body.tier, diet=body.diet, ingredients=body.ingredients,
                          recipe=recipe, mode=result.mode, fallback_used=result.fallback_used,
                          cache_hit=result.cache_hits["recipe"], latency_ms=ms, gen_model=scratch.get("generation")))
    record_event(session, identity.owner_id, meta.ip_hash, "recipe", tier=body.tier, found=recipe is not None,
                 fallback=result.fallback_used, cache=result.cache_hits["recipe"], ms=ms)
    session.commit()
    return {
        "run_id": run_id, "recipe": recipe, "suggestions": result.suggestions, "fallback_used": result.fallback_used,
        "alternatives": [recipe_payload(a, svc.recipes) for a in result.alternatives], "mode": result.mode,
        "scores": {k: round(float(v), 3) for k, v in result.scores.items()}, "candidates": result.candidates,
        "timings": {k: round(v, 2) for k, v in result.timings.items()}, "cache_hits": result.cache_hits,
        "latency_ms": ms,
    }
