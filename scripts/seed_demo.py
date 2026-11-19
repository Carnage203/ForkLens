"""Fill the database with realistic fake traffic so the admin dashboard has something to show (reports/demos).

Usage:  python -m scripts.seed_demo --yes [--days 14]
Rows use owner ids starting with ``g_demo`` so they are easy to delete:  DELETE FROM owners WHERE id LIKE 'g_demo%'.
"""
from __future__ import annotations

import argparse
import random
import uuid
from datetime import timedelta

from backend.db.models import Event, Feedback, Owner, RecipeRun, RequestLog, day_of, utcnow
from backend.db.session import Database
from forklens.config import Settings

INGREDIENTS = ["egg", "bread", "rice", "oats", "banana", "potato", "onion", "tomato", "paneer", "milk", "noodles", "curd"]
TITLES = ["Kettle Masala Oats", "Egg Bhurji Toast", "Tomato Rice", "Banana Oat Bowl", "Curd Rice", "Paneer Wrap"]
MODELS = ["groq:qwen/qwen3.8-27b", "groq:openai/gpt-oss-20b", "gemini-3.6-flash", None]
COUNTRIES = ["IN", "IN", "IN", "US", "GB", "SG", "AE"]


def main() -> None:
    """Insert fake owners, requests, events, recipe runs and feedback spread over the last N days."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="confirm writing demo rows")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Refusing to write demo data without --yes")
    db = Database(Settings.load().database_url)
    db.create_all()
    rng = random.Random(7)
    with db.session() as session:
        for n in range(60):
            created = utcnow() - timedelta(days=rng.randint(0, args.days - 1), hours=rng.randint(0, 23))
            owner = f"g_demo{n:03d}{uuid.uuid4().hex[:8]}"
            session.add(Owner(id=owner, kind="guest", country=rng.choice(COUNTRIES), created_at=created, last_seen_at=created, request_count=0))
            for _ in range(rng.randint(1, 6)):
                ts = created + timedelta(minutes=rng.randint(0, 600))
                day, tier = day_of(ts), rng.choice(["hostel", "hostel", "pg", "home"])
                ingredients = rng.sample(INGREDIENTS, rng.randint(2, 5))
                ok = rng.random() > 0.08
                ms = int(rng.lognormvariate(7.4, 0.5))
                session.add(RequestLog(ts=ts, day=day, request_id=uuid.uuid4().hex[:8], method="POST", path="/api/scan", status=200, duration_ms=ms, owner_id=owner))
                session.add(Event(ts=ts, day=day, type="scan", owner_id=owner, data={"photos": 1, "found": len(ingredients), "ms": ms, "model": rng.choice(MODELS[:3])}))
                session.add(RequestLog(ts=ts, day=day, request_id=uuid.uuid4().hex[:8], method="POST", path="/api/recipes/generate", status=200 if ok else 503,
                                       duration_ms=ms + 600, owner_id=owner, error=None if ok else "generation_unavailable: AI busy"))
                if ok:
                    run = uuid.uuid4().hex[:12]
                    title = rng.choice(TITLES)
                    session.add(RecipeRun(id=run, owner_id=owner, ts=ts, day=day, tier=tier, diet="any", ingredients=ingredients, mode="live/gemini",
                                          recipe={"title": title}, fallback_used=rng.random() < 0.05, cache_hit=rng.random() < 0.3,
                                          latency_ms=ms + 600, gen_model=rng.choice(MODELS)))
                    session.add(Event(ts=ts, day=day, type="recipe", owner_id=owner, data={"tier": tier}))
                    if rng.random() < 0.35:
                        session.add(Event(ts=ts, day=day, type="cooked", owner_id=owner, data={"title": title}))
                    if rng.random() < 0.3:
                        session.add(Feedback(ts=ts, owner_id=owner, run_id=run, rating=rng.choice([5, 5, 5, 4, 3, 1]), comment=""))
        session.commit()
    print("Demo data inserted.")


if __name__ == "__main__":
    main()
