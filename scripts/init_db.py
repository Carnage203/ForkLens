"""Create the database tables (idempotent). Run once after setting DATABASE_URL:  python -m scripts.init_db"""
from __future__ import annotations

from backend.db.session import Database
from forklens.config import Settings


def main() -> None:
    """Connect using DATABASE_URL (or the local SQLite file) and create every missing table."""
    settings = Settings.load()
    db = Database(settings.database_url)
    db.create_all()
    print(f"Tables ready on {db.dialect}. Connection check: {'ok' if db.ping() else 'FAILED'}")


if __name__ == "__main__":
    main()
