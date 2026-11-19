"""Pipeline: orchestrates vision -> retrieval -> generation. All collaborators are injected."""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Sequence

import pandas as pd

from forklens.analytics.series import ingredient_series, merge_ingredient_series, score_series
from forklens.cache import Cache
from forklens.config import Settings
from forklens.exceptions import GenerationError, NoIngredientsDetectedError
from forklens.limiter import RateLimiter
from forklens.models import Conditions, GeneratedRecipe, PipelineResult
from forklens.rag.generator import GenerationContext, Generator, VerbatimGenerator, recipe_to_generated
from forklens.rag.retriever import Retriever
from forklens.tiers import Tier
from forklens.vision.base import VisionProvider
from forklens.vision.image_utils import PreparedImage
from forklens.vision.normalizer import IngredientNormalizer

log = logging.getLogger("forklens.pipeline")


class Pipeline:
    """Orchestrator; every dependency arrives through the constructor (easy to mock)."""

    def __init__(self, vision: VisionProvider, retriever: Retriever, generator: Generator,
                 normalizer: IngredientNormalizer, cache: Cache, limiter: RateLimiter,
                 settings: Settings, fallback_generator: Generator | None = None,
                 scan_limiter: RateLimiter | None = None) -> None:
        self._vision, self._retriever, self._generator = vision, retriever, generator
        self._normalizer, self._cache, self._limiter, self._settings = normalizer, cache, limiter, settings
        self._fallback = fallback_generator or VerbatimGenerator()
        self._scan_limiter = scan_limiter

    @property
    def mode(self) -> str:
        """'live' when the vision provider is not the mock."""
        return "mock" if self._vision.name == "mock" else "live"

    def detect(self, image: PreparedImage, session_id: str = "") -> tuple[pd.Series, bool]:
        """Detect ingredients (cached by image hash). Returns (Series, cache_hit). Only cache misses use quota."""
        key = f"vision:{self._vision.name}:{image.sha256}"
        cached = self._cache.get(key)
        if cached is not None:
            return pd.Series(cached, name="confidence", dtype=float), True
        if self._scan_limiter is not None:
            self._scan_limiter.check(session_id)
        items = self._normalizer.normalize_all(self._vision.detect(image.data))
        series = ingredient_series(items)
        if series.empty:
            raise NoIngredientsDetectedError("No ingredients left after normalisation")
        self._cache.set(key, series.to_dict(), self._settings.vision_ttl_s)
        return series, False

    def detect_many(self, images: Sequence[PreparedImage], session_id: str = "") -> tuple[pd.Series, int]:
        """Detect across several photos (each cached) and merge. Returns (Series, photos_with_no_items).

        A photo with nothing recognisable is skipped; the call fails only if every photo is empty.
        """
        def run(image: PreparedImage) -> pd.Series | None:
            try:
                return self.detect(image, session_id)[0]
            except NoIngredientsDetectedError:
                return None

        batch = list(images[: self._settings.max_photos])
        with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:  # photos are independent API calls
            futures = [pool.submit(contextvars.copy_context().run, run, image) for image in batch]
            results = [future.result() for future in futures]
        parts = [r for r in results if r is not None]
        empty = len(results) - len(parts)
        merged = merge_ingredient_series(parts)
        if merged.empty:
            raise NoIngredientsDetectedError("No ingredients found in any photo")
        return merged, empty

    @staticmethod
    def _recipe_key(tier: Tier, ingredients: list[str], extras: list[str], conditions: Conditions) -> str:
        payload = json.dumps([tier.name, sorted(tier.allowed_equipment), ingredients, extras,
                              conditions.diet, conditions.max_time])
        return "recipe:" + hashlib.sha256(payload.encode()).hexdigest()

    def recommend(self, ingredients: Iterable[str], tier: Tier, conditions: Conditions,
                  extras: Iterable[str], session_id: str) -> PipelineResult:
        """Retrieve, rerank and generate a recipe for the (user-edited) ingredient list."""
        timings: dict[str, float] = {}
        names = sorted({n for n in (self._normalizer.normalize(i) for i in ingredients) if n})
        if not names:
            raise NoIngredientsDetectedError("The ingredient list is empty")
        extra_names = sorted(self._normalizer.normalize(e) for e in extras) if tier.allow_extra_supplies else []
        series = pd.Series(1.0, index=names, name="confidence")

        key = self._recipe_key(tier, names, extra_names, conditions)
        cached = self._cache.get(key)
        if cached is not None:
            return self._from_cache(cached, series)

        start = time.perf_counter()
        result = self._retriever.search(set(names), tier, conditions, set(extra_names))
        timings["retrieve_s"] = time.perf_counter() - start
        available = frozenset(tier.available(names, extra_names))
        fallback_used = False
        recipe: GeneratedRecipe | None = None
        alternatives: list[GeneratedRecipe] = []
        if result.recipes:
            ctx = GenerationContext(tier, conditions, available, tuple(result.recipes))
            self._limiter.check(session_id)
            start = time.perf_counter()
            try:
                recipe = self._generator.generate(ctx)
            except GenerationError as exc:
                log.warning("Generator failed (%s); using verbatim fallback", exc.message)
                recipe = self._fallback.generate(ctx)
                fallback_used = True
            timings["generate_s"] = time.perf_counter() - start
            used = set(recipe.source_recipe_ids)
            alternatives = [recipe_to_generated(s, ctx) for s in result.recipes if s.recipe.id not in used][:2]

        candidates = [{"id": s.recipe.id, "title": s.recipe.title, "similarity": round(s.similarity, 3),
                       "coverage": round(s.coverage, 2), "missing": list(s.missing), "score": round(s.score, 3)}
                      for s in result.recipes]
        out = PipelineResult(recipe, series, result.scores, timings,
                             {"query_embedding": result.cache_hit, "recipe": False},
                             fallback_used, result.suggestions, candidates, f"{self.mode}/{result.embedder}", alternatives)
        self._cache.set(key, out.to_cache(), self._settings.recipe_ttl_s)
        return out

    def _from_cache(self, cached: dict, series: pd.Series) -> PipelineResult:
        recipe = GeneratedRecipe(**cached["recipe"]) if cached["recipe"] else None
        scores = score_series(cached["scores"].items())
        return PipelineResult(recipe, series, scores, {}, {"query_embedding": False, "recipe": True},
                              cached["fallback_used"], cached["suggestions"], cached["candidates"], cached["mode"],
                              [GeneratedRecipe(**a) for a in cached.get("alternatives", [])])
