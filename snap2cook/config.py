"""Application settings read from environment variables or a local .env (never hardcoded)."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


def _csv(value: str) -> tuple[str, ...]:
    """Split a comma-separated setting into a tuple of non-empty items."""
    return tuple(m.strip() for m in value.split(",") if m.strip())


@dataclass(frozen=True)
class Settings:
    """Immutable configuration. Every secret is hidden from ``repr``."""

    env: str = "dev"
    database_url: str = field(default="", repr=False)
    supabase_url: str = ""
    supabase_anon_key: str = ""  # public by design (shipped to the browser)
    admin_username: str = ""
    admin_password: str = field(default="", repr=False)
    admin_jwt_secret: str = field(default="", repr=False)
    cron_secret: str = field(default="", repr=False)
    corpus_source: str = "local"  # "local" (fast cold start) or "cloud" (Hugging Face, local fallback)
    allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    guest_gen_limit: int = 6
    user_gen_limit: int = 20
    guest_scan_limit: int = 12
    user_scan_limit: int = 40
    ip_limit_factor: int = 3

    gemini_api_key: str = field(default="", repr=False)
    vision_model: str = "gemini-4-hydrogen"
    gen_model: str = "gemini-3.6-flash"
    fallback_models: tuple[str, ...] = ("gemini-3.6-flash",)
    groq_api_key: str = field(default="", repr=False)
    openrouter_api_key: str = field(default="", repr=False)
    groq_vision_models: tuple[str, ...] = ("qwen/qwen3.8-27b",)
    openrouter_vision_models: tuple[str, ...] = ("anthropic/claude-haiku-5.5",)
    groq_gen_models: tuple[str, ...] = ("openai/gpt-oss-20b", "qwen/qwen3.8-27b")
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    hf_dataset_repo: str = ""
    data_dir: Path = ROOT / "data"
    cache_dir: Path = Path(tempfile.gettempdir()) / "snap2cook_cache"
    log_dir: Path = ROOT / "logs"
    w_similarity: float = 0.6
    w_coverage: float = 0.4
    w_missing: float = 0.1
    rate_limit_calls: int = 6
    rate_limit_window_s: int = 600
    daily_limit: int = 300
    max_photos: int = 3
    api_timeout_s: int = 15
    api_retries: int = 2
    vision_ttl_s: int = 7 * 24 * 3600
    recipe_ttl_s: int = 24 * 3600

    @property
    def live_mode(self) -> bool:
        """True when a Gemini key is configured."""
        return bool(self.gemini_api_key)

    @property
    def admin_enabled(self) -> bool:
        """The admin console exists only when username, password and a strong JWT secret are all set."""
        return bool(self.admin_username and self.admin_password and len(self.admin_jwt_secret) >= 24)

    @property
    def auth_enabled(self) -> bool:
        """Supabase login is offered only when both its URL and public key are configured."""
        return bool(self.supabase_url and self.supabase_anon_key)

    @classmethod
    def load(cls, overrides: Mapping[str, str] | None = None) -> "Settings":
        """Build settings: st.secrets, then os.environ, then .env (local only)."""
        dotenv = dotenv_values(ROOT / ".env")

        def get(key: str, default: str = "") -> str:
            if overrides and overrides.get(key):
                return str(overrides[key])
            for source in (os.environ.get(key), dotenv.get(key)):
                if source:
                    return str(source)
            return default

        defaults = cls()
        return cls(
            gemini_api_key=get("GEMINI_API_KEY"),
            vision_model=get("VISION_MODEL", defaults.vision_model),
            gen_model=get("GEN_MODEL", defaults.gen_model),
            fallback_models=_csv(get("FALLBACK_MODELS", ",".join(defaults.fallback_models))),
            groq_api_key=get("GROQ_API_KEY"),
            openrouter_api_key=get("OPENROUTER_API_KEY") or get("Open_Router_API_KEY"),
            groq_vision_models=_csv(get("GROQ_VISION_MODELS", ",".join(defaults.groq_vision_models))),
            openrouter_vision_models=_csv(get("OPENROUTER_VISION_MODELS", ",".join(defaults.openrouter_vision_models))),
            groq_gen_models=_csv(get("GROQ_GEN_MODELS", ",".join(defaults.groq_gen_models))),
            embed_model=get("EMBED_MODEL", defaults.embed_model),
            embed_dim=int(get("EMBED_DIM", str(defaults.embed_dim))),
            hf_dataset_repo=get("HF_DATASET_REPO"),
            env="prod" if (get("VERCEL") or get("APP_ENV") == "prod") else "dev",
            database_url=get("DATABASE_URL"),
            supabase_url=get("SUPABASE_URL").rstrip("/"),
            supabase_anon_key=get("SUPABASE_ANON_KEY"),
            admin_username=get("ADMIN_USERNAME"),
            admin_password=get("ADMIN_PASSWORD"),
            admin_jwt_secret=get("ADMIN_JWT_SECRET"),
            cron_secret=get("CRON_SECRET"),
            corpus_source=get("CORPUS_SOURCE", defaults.corpus_source),
            allowed_origins=_csv(get("ALLOWED_ORIGINS", ",".join(defaults.allowed_origins))),
            guest_gen_limit=int(get("GUEST_GEN_LIMIT", str(defaults.guest_gen_limit))),
            user_gen_limit=int(get("USER_GEN_LIMIT", str(defaults.user_gen_limit))),
        )
