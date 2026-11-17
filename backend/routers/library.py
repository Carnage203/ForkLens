"""Per-user library: saved recipes, history, pantry, shopping list, feedback, profile."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.db.models import (Event, Feedback, PantryItem, RecipeRun, SavedRecipe, ShoppingItem, day_of, utcnow)
from backend.deps import ClientMeta, Identity, get_identity, get_meta, get_services, get_session
from backend.schemas import FeedbackIn, PantryIn, SaveIn, ShareIn, ShoppingIn, ShoppingPatch
from backend.services.helpers import new_id, record_event
from backend.services.hub import Services

router = APIRouter(prefix="/api")


def _saved(row: SavedRecipe) -> dict:
    return {"id": row.id, "title": row.title, "tier": row.tier, "recipe": row.recipe, "cooked_count": row.cooked_count,
            "created_at": row.created_at.isoformat(), "share_token": row.share_token}


def _own_saved(session: Session, identity: Identity, saved_id: str) -> SavedRecipe:
    row = session.get(SavedRecipe, saved_id)
    if row is None or row.owner_id != identity.owner_id:
        raise HTTPException(404, "Recipe not found")
    return row


# ---- saved recipes -------------------------------------------------------------------------------------------
@router.get("/saved")
def list_saved(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """Bookmarked recipes, newest first."""
    rows = session.scalars(select(SavedRecipe).where(SavedRecipe.owner_id == identity.owner_id)
                           .order_by(SavedRecipe.created_at.desc()).limit(200))
    return [_saved(r) for r in rows]


@router.post("/saved", status_code=201)
def save_recipe(body: SaveIn, identity: Identity = Depends(get_identity), session: Session = Depends(get_session),
                meta: ClientMeta = Depends(get_meta)) -> dict:
    """Bookmark a recipe (saving the same title twice returns the existing bookmark)."""
    existing = session.scalar(select(SavedRecipe).where(SavedRecipe.owner_id == identity.owner_id,
                                                         SavedRecipe.title == body.recipe.title))
    if existing:
        return _saved(existing)
    row = SavedRecipe(id=new_id(), owner_id=identity.owner_id, title=body.recipe.title, tier=body.tier,
                      recipe=body.recipe.model_dump())
    session.add(row)
    record_event(session, identity.owner_id, meta.ip_hash, "save", tier=body.tier)
    session.commit()
    return _saved(row)


@router.delete("/saved/{saved_id}", status_code=204)
def delete_saved(saved_id: str, identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> None:
    """Remove a bookmark."""
    session.delete(_own_saved(session, identity, saved_id))
    session.commit()


@router.post("/saved/{saved_id}/cooked")
def mark_cooked(saved_id: str, identity: Identity = Depends(get_identity), session: Session = Depends(get_session),
                meta: ClientMeta = Depends(get_meta)) -> dict:
    """'I cooked this': counts towards cook points and the daily streak."""
    row = _own_saved(session, identity, saved_id)
    row.cooked_count, row.last_cooked_at = row.cooked_count + 1, utcnow()
    record_event(session, identity.owner_id, meta.ip_hash, "cooked", title=row.title)
    session.commit()
    return _saved(row)


@router.post("/saved/{saved_id}/share")
def share(saved_id: str, body: ShareIn, identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> dict:
    """Create or revoke the public read-only link ``/r/<token>``."""
    row = _own_saved(session, identity, saved_id)
    row.share_token = (row.share_token or secrets.token_urlsafe(9)) if body.enabled else None
    session.commit()
    return _saved(row)


@router.get("/shared/{token}")
def shared(token: str, session: Session = Depends(get_session)) -> dict:
    """Public recipe page (no identity needed; never exposes the owner)."""
    row = session.scalar(select(SavedRecipe).where(SavedRecipe.share_token == token))
    if row is None:
        raise HTTPException(404, "This shared recipe is no longer available")
    return {"title": row.title, "tier": row.tier, "recipe": row.recipe}


# ---- history ------------------------------------------------------------------------------------------------
@router.get("/history")
def history(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """The caller's last 40 recipe requests."""
    rows = session.scalars(select(RecipeRun).where(RecipeRun.owner_id == identity.owner_id)
                           .order_by(RecipeRun.ts.desc()).limit(40))
    return [{"id": r.id, "ts": r.ts.isoformat(), "tier": r.tier, "diet": r.diet, "ingredients": r.ingredients,
             "recipe": r.recipe} for r in rows if r.recipe]


@router.delete("/history", status_code=204)
def clear_history(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> None:
    """Delete the caller's history."""
    session.execute(delete(RecipeRun).where(RecipeRun.owner_id == identity.owner_id))
    session.commit()


# ---- pantry -------------------------------------------------------------------------------------------------
@router.get("/pantry")
def get_pantry(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """Ingredients the user keeps at home."""
    rows = session.scalars(select(PantryItem).where(PantryItem.owner_id == identity.owner_id).order_by(PantryItem.name))
    return [{"name": r.name, "use_by": r.use_by} for r in rows]


@router.put("/pantry")
def put_pantry(body: PantryIn, identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """Replace the pantry with the given list."""
    session.execute(delete(PantryItem).where(PantryItem.owner_id == identity.owner_id))
    unique = {i.name.strip().lower(): i.use_by for i in body.items if i.name.strip()}
    session.add_all(PantryItem(owner_id=identity.owner_id, name=n, use_by=u) for n, u in unique.items())
    session.commit()
    return [{"name": n, "use_by": u} for n, u in sorted(unique.items())]


# ---- shopping list ------------------------------------------------------------------------------------------
def _item(r: ShoppingItem) -> dict:
    return {"id": r.id, "name": r.name, "checked": r.checked, "source": r.source}


@router.get("/shopping")
def get_shopping(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """Shopping list (unchecked first)."""
    rows = session.scalars(select(ShoppingItem).where(ShoppingItem.owner_id == identity.owner_id)
                           .order_by(ShoppingItem.checked, ShoppingItem.created_at.desc()))
    return [_item(r) for r in rows]


@router.post("/shopping", status_code=201)
def add_shopping(body: ShoppingIn, identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> list[dict]:
    """Add items, skipping names already on the list."""
    have = set(session.scalars(select(ShoppingItem.name).where(ShoppingItem.owner_id == identity.owner_id)))
    fresh = [n for n in dict.fromkeys(body.names) if n not in have]
    session.add_all(ShoppingItem(id=new_id(), owner_id=identity.owner_id, name=n, source=body.source) for n in fresh)
    session.commit()
    return get_shopping(identity, session)


@router.patch("/shopping/{item_id}")
def patch_shopping(item_id: str, body: ShoppingPatch, identity: Identity = Depends(get_identity),
                   session: Session = Depends(get_session)) -> dict:
    """Tick or untick an item."""
    row = session.get(ShoppingItem, item_id)
    if row is None or row.owner_id != identity.owner_id:
        raise HTTPException(404, "Item not found")
    row.checked = body.checked
    session.commit()
    return _item(row)


@router.delete("/shopping", status_code=204)
def clear_shopping(checked_only: bool = True, identity: Identity = Depends(get_identity),
                   session: Session = Depends(get_session)) -> None:
    """Remove ticked items (default) or everything."""
    query = delete(ShoppingItem).where(ShoppingItem.owner_id == identity.owner_id)
    session.execute(query.where(ShoppingItem.checked.is_(True)) if checked_only else query)
    session.commit()


# ---- feedback and profile -----------------------------------------------------------------------------------
@router.post("/feedback", status_code=201)
def feedback(body: FeedbackIn, identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> dict:
    """Store a rating (powers the admin satisfaction chart)."""
    session.add(Feedback(owner_id=identity.owner_id, run_id=body.run_id, rating=body.rating, category=body.category,
                         comment=body.comment.strip()))
    session.commit()
    return {"ok": True}


def streak_days(days: set[str]) -> int:
    """Consecutive days (ending today or yesterday) on which something was cooked."""
    cursor = utcnow()
    if day_of(cursor) not in days:
        cursor -= timedelta(days=1)
    count = 0
    while day_of(cursor) in days:
        count, cursor = count + 1, cursor - timedelta(days=1)
    return count


@router.get("/me")
def me(identity: Identity = Depends(get_identity), session: Session = Depends(get_session),
       svc: Services = Depends(get_services)) -> dict:
    """Profile, cook points and streak."""
    owner = identity.owner_id
    count = lambda model, *where: session.scalar(select(func.count()).select_from(model).where(*where)) or 0  # noqa: E731
    cooked_days = set(session.scalars(select(Event.day).where(Event.owner_id == owner, Event.type == "cooked").distinct()))
    cooked = count(Event, Event.owner_id == owner, Event.type == "cooked")
    runs = count(RecipeRun, RecipeRun.owner_id == owner)
    limit = svc.settings.user_gen_limit if identity.is_user else svc.settings.guest_gen_limit
    return {"kind": "user" if identity.is_user else "guest", "email": identity.email, "name": identity.name,
            "stats": {"saved": count(SavedRecipe, SavedRecipe.owner_id == owner), "cooked": cooked, "recipes": runs,
                      "streak": streak_days(cooked_days), "points": cooked * 10 + runs},
            "generation_limit": limit}


@router.post("/me/claim")
def claim(identity: Identity = Depends(get_identity), session: Session = Depends(get_session)) -> dict:
    """After sign-in, move everything created as a guest on this browser to the account."""
    guest = identity.guest_id
    if not identity.is_user or not guest:
        return {"moved": 0}
    moved = 0
    for model in (SavedRecipe, ShoppingItem, RecipeRun, Feedback):
        moved += session.execute(update(model).where(model.owner_id == guest).values(owner_id=identity.owner_id)).rowcount or 0
    mine = set(session.scalars(select(PantryItem.name).where(PantryItem.owner_id == identity.owner_id)))
    session.execute(delete(PantryItem).where(PantryItem.owner_id == guest, PantryItem.name.in_(mine or [""])))
    moved += session.execute(update(PantryItem).where(PantryItem.owner_id == guest).values(owner_id=identity.owner_id)).rowcount or 0
    session.commit()
    return {"moved": moved}
