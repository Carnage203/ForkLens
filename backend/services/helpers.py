"""Small helpers shared by routers: event recording, recipe payloads, ids."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import Event
from snap2cook.models import GeneratedRecipe, Recipe


def new_id() -> str:
    """Short unique id (12 hex chars)."""
    return uuid.uuid4().hex[:12]


def record_event(session: Session, owner_id: str | None, ip_hash: str | None, type_: str, **data: Any) -> None:
    """Append a product-analytics event (committed by the caller's transaction)."""
    session.add(Event(type=type_, owner_id=owner_id, ip_hash=ip_hash, data=data))


def recipe_payload(recipe: GeneratedRecipe, corpus: dict[str, Recipe]) -> dict[str, Any]:
    """Recipe as JSON, enriched with calories/cuisine/diet/difficulty from the first source recipe."""
    payload = recipe.model_dump()
    source = next((corpus[i] for i in recipe.source_recipe_ids if i in corpus), None)
    payload["meta"] = ({"calories": source.calories, "cuisine": source.cuisine, "diet": source.diet,
                        "difficulty": source.difficulty} if source else None)
    return payload
