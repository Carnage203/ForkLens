"""Composition root: wires concrete classes into a Pipeline (used by the API and scripts)."""
from __future__ import annotations

from dataclasses import dataclass

from forklens.cache import Cache, FileCache, LRUCache, TieredCache
from forklens.config import Settings
from forklens.gemini import build_client, model_chain
from forklens.llm import GROQ_PREFIX, OPENROUTER_PREFIX, GroqClient, OpenRouterClient
from forklens.limiter import RateLimiter
from forklens.pipeline import Pipeline
from forklens.rag.corpus import Corpus
from forklens.rag.embedder import GeminiEmbedder, LexicalEmbedder
from forklens.rag.generator import GeminiGenerator, VerbatimGenerator
from forklens.rag.reranker import CoverageReranker
from forklens.rag.retriever import Retriever
from forklens.rag.store import HFDatasetStore, LocalStore, load_with_fallback
from forklens.tiers import Pantry
from forklens.vision.gemini_provider import GeminiVisionProvider
from forklens.vision.mock_provider import MockVisionProvider
from forklens.vision.normalizer import IngredientNormalizer


@dataclass(frozen=True)
class App:
    """Long-lived objects shared by every request served by one process."""

    settings: Settings
    pipeline: Pipeline
    pantry: Pantry
    cache: Cache
    limiter: RateLimiter
    vocabulary: list[str]
    corpus_source: str
    corpus: Corpus


def build_app(settings: Settings, cache: Cache | None = None, limiter: RateLimiter | None = None,
              scan_limiter: RateLimiter | None = None) -> App:
    """Create everything. Live mode needs a key; otherwise mock providers are used.

    ``cache``/``limiter``/``scan_limiter`` are injected by the API (database backed); defaults suit scripts.
    """
    local = LocalStore(settings)
    corpus = local.load() if settings.corpus_source == "local" else load_with_fallback(HFDatasetStore(settings), local)
    vocabulary = sorted(corpus.vocabulary)
    pantry = Pantry.load(settings.data_dir / "pantry.json")
    normalizer = IngredientNormalizer.from_file(settings.data_dir / "synonyms.json", vocabulary)
    cache = cache or TieredCache(LRUCache(512), FileCache(settings.cache_dir))
    limiter = limiter or RateLimiter(settings.rate_limit_calls, settings.rate_limit_window_s, settings.daily_limit)
    lexical = LexicalEmbedder(vocabulary)
    reranker = CoverageReranker.from_settings(settings)
    if settings.live_mode:
        client = build_client(settings)
        groq = GroqClient(settings.groq_api_key) if settings.groq_api_key else None
        openrouter = OpenRouterClient(settings.openrouter_api_key) if settings.openrouter_api_key else None
        # Fastest first (Groq vision), then Gemini Hydrogen, then OpenRouter as the last resort.
        vision_models = tuple(dict.fromkeys((
            *(f"{GROQ_PREFIX}{m}" for m in settings.groq_vision_models if groq),
            settings.vision_model,
            *(f"{OPENROUTER_PREFIX}{m}" for m in settings.openrouter_vision_models if openrouter))))
        chat_clients = {c.prefix: c for c in (groq, openrouter) if c}
        # Groq answers fast, so it does all generation; Gemini is only the fallback when no Groq key is set.
        gen_models = (tuple(f"{GROQ_PREFIX}{m}" for m in settings.groq_gen_models) if groq
                      else model_chain(settings.gen_model, settings.fallback_models))
        vision = GeminiVisionProvider(client, vision_models, settings.api_retries, chat_clients)
        embedder = GeminiEmbedder(client, settings.embed_model, settings.embed_dim, settings.api_retries)
        generator = GeminiGenerator(client, gen_models, settings.api_retries, groq)
    else:
        vision, embedder, generator = MockVisionProvider(), lexical, VerbatimGenerator()
    retriever = Retriever(corpus, embedder, reranker, lexical, cache)
    pipeline = Pipeline(vision, retriever, generator, normalizer, cache, limiter, settings,
                        scan_limiter=scan_limiter)
    return App(settings, pipeline, pantry, cache, limiter, vocabulary, corpus.source, corpus)
