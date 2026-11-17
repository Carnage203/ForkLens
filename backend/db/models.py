"""SQLAlchemy ORM models. One schema, two engines: SQLite for local dev/tests, Postgres (Supabase) in production."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def utcnow() -> datetime:
    """Naive UTC timestamp (all columns store UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def day_of(moment: datetime | None = None) -> str:
    """'YYYY-MM-DD' bucket used for cheap, portable GROUP BY day."""
    return (moment or utcnow()).strftime("%Y-%m-%d")


class Base(DeclarativeBase):
    """Declarative base."""


class Owner(Base):
    """Anyone using the app: a registered user (Supabase uuid) or an anonymous guest (``g_<client id>``)."""

    __tablename__ = "owners"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), index=True)  # "user" | "guest"
    email: Mapped[str | None] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)


class RequestLog(Base):
    """One row per API request (written after the response is sent)."""

    __tablename__ = "request_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    day: Mapped[str] = mapped_column(String(10), default=day_of, index=True)
    request_id: Mapped[str] = mapped_column(String(16))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[int] = mapped_column(Integer, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(16))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    error: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    """Product analytics and quota ledger (``quota:*`` rows power the database rate limiter)."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_owner_type_ts", "owner_id", "type", "ts"),
                      Index("ix_events_ip_type_ts", "ip_hash", "type", "ts"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    day: Mapped[str] = mapped_column(String(10), default=day_of, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    owner_id: Mapped[str | None] = mapped_column(String(80))
    ip_hash: Mapped[str | None] = mapped_column(String(16))
    data: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class CacheEntry(Base):
    """L2 cache shared by every serverless instance (vision by image hash, recipes, query embeddings)."""

    __tablename__ = "cache_entries"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JsonType)
    expires_at: Mapped[float] = mapped_column(Float, index=True)


class RecipeRun(Base):
    """One recipe request and its outcome: powers History and the admin analytics."""

    __tablename__ = "recipe_runs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    day: Mapped[str] = mapped_column(String(10), default=day_of, index=True)
    tier: Mapped[str] = mapped_column(String(8))
    diet: Mapped[str] = mapped_column(String(10))
    ingredients: Mapped[list[str]] = mapped_column(JsonType, default=list)
    recipe: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    mode: Mapped[str] = mapped_column(String(60), default="")
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    gen_model: Mapped[str | None] = mapped_column(String(80))


class SavedRecipe(Base):
    """A recipe the user bookmarked; optionally shared through an unguessable token."""

    __tablename__ = "saved_recipes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    tier: Mapped[str] = mapped_column(String(8), default="home")
    recipe: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cooked_count: Mapped[int] = mapped_column(Integer, default=0)
    last_cooked_at: Mapped[datetime | None] = mapped_column(DateTime)
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True)


class PantryItem(Base):
    """An ingredient the user keeps at home (optionally with a use-by date)."""

    __tablename__ = "pantry_items"
    owner_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    use_by: Mapped[str | None] = mapped_column(String(10))


class ShoppingItem(Base):
    """A line of the shopping list (usually the 'extra needed' of a recipe)."""

    __tablename__ = "shopping_items"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(60))
    source: Mapped[str | None] = mapped_column(String(200))
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Feedback(Base):
    """Thumbs / star rating and free text from users."""

    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    owner_id: Mapped[str] = mapped_column(String(80), index=True)
    run_id: Mapped[str | None] = mapped_column(String(16))
    rating: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20), default="recipe")
    comment: Mapped[str] = mapped_column(Text, default="")
