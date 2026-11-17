"""Request bodies. Strict limits here are the first line of defence against abuse and bad input."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Name = Field(min_length=1, max_length=40)


def _clean(values: list[str]) -> list[str]:
    return [v.strip().lower() for v in values if v and v.strip()]


class GenerateIn(BaseModel):
    """Ask for a recipe from a (user-edited) ingredient list."""

    ingredients: list[str] = Field(min_length=1, max_length=40)
    tier: Literal["hostel", "pg", "home"] = "home"
    equipment: list[str] = Field(default_factory=list, max_length=4)
    extras: list[str] = Field(default_factory=list, max_length=40)
    diet: Literal["any", "veg", "vegan", "egg", "non-veg"] = "any"
    max_time: int | None = Field(default=None, ge=5, le=240)

    _norm = field_validator("ingredients", "extras", "equipment", mode="after")(_clean)

    @field_validator("ingredients", "extras")
    @classmethod
    def _length(cls, values: list[str]) -> list[str]:
        if any(len(v) > 40 for v in values):
            raise ValueError("name too long")
        return values


class RecipeIn(BaseModel):
    """A recipe as displayed to the user (what the client sends back to save or share)."""

    title: str = Field(min_length=1, max_length=200)
    time_min: int = Field(ge=0, le=1440)
    ingredients_used: list[str] = Field(max_length=60)
    extra_needed: list[str] = Field(max_length=20)
    techniques_used: list[str] = Field(max_length=20)
    steps: list[str] = Field(min_length=1, max_length=40)
    substitutions: list[str] = Field(max_length=20)
    safety_note: str = Field(max_length=500)
    source_recipe_ids: list[str] = Field(max_length=10)
    meta: dict | None = None


class SaveIn(BaseModel):
    """Bookmark a recipe."""

    recipe: RecipeIn
    tier: Literal["hostel", "pg", "home"] = "home"


class ShareIn(BaseModel):
    """Turn the public share link on or off."""

    enabled: bool


class PantryEntry(BaseModel):
    """One pantry line."""

    name: str = Name
    use_by: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PantryIn(BaseModel):
    """Replace the whole pantry."""

    items: list[PantryEntry] = Field(max_length=120)


class ShoppingIn(BaseModel):
    """Add names to the shopping list."""

    names: list[str] = Field(min_length=1, max_length=30)
    source: str | None = Field(default=None, max_length=200)

    _norm = field_validator("names", mode="after")(_clean)


class ShoppingPatch(BaseModel):
    """Tick or untick a shopping item."""

    checked: bool


class FeedbackIn(BaseModel):
    """Rating and optional comment."""

    rating: int = Field(ge=1, le=5)
    category: Literal["recipe", "scan", "app"] = "recipe"
    comment: str = Field(default="", max_length=500)
    run_id: str | None = Field(default=None, max_length=16)


class AdminLoginIn(BaseModel):
    """Admin credentials."""

    username: str = Field(max_length=100)
    password: str = Field(max_length=200)
